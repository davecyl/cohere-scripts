# #########################################################################
# Copyright (c) , UChicago Argonne, LLC. All rights reserved.             #
#                                                                         #
# See LICENSE file.                                                       #
# #########################################################################

"""
This user script manages reconstruction(s).
Depending on configuration it starts either single reconstruction, GA, or multiple reconstructions. In multiple reconstruction scenario or split scans the script runs concurrent reconstructions.
"""

__author__ = "Barbara Frosik"
__copyright__ = "Copyright (c), UChicago Argonne, LLC."
__docformat__ = 'restructuredtext en'
__all__ = ['interrupt_thread',
           'rec_process',
           'get_gpu_use',
           'manage_reconstruction',
           'main']

import sys
import signal
import os
import argparse
import numpy as np
from multiprocessing import Process, Queue
import cohere.src_py.controller.reconstruction as rec
import cohere.src_py.controller.gen_rec as gen_rec
import cohere.src_py.controller.reconstruction_multi as mult_rec
import cohere.src_py.utilities.utils as ut
import config_verifier as ver
import time
import convertconfig as conv

MEM_FACTOR = 1500
ADJUST = 0.0


def interrupt_thread():
    """
    This function is part of interrupt mechanism. It detects ctl-c signal and creates an empty file named "stopfile".
    The file is discovered by fast module processand the discovery prompts termination of that process.
    """

    def int_handler(signal, frame):
        while not os.path.isfile('stopfile'):
            open('stopfile', 'a').close()
            time.sleep(.3)

        # #remove the file at the end
        if os.path.isfile('stopfile'):
            os.remove('stopfile')

    def term_handler(signal, frame):
        pass

    signal.signal(signal.SIGINT, int_handler)
    signal.signal(signal.SIGTERM, term_handler)
    signal.pause()


def rec_process(proc, conf_file, datafile, dir, gpus, r, q):
    """
    Calls the reconstruction function in a module identified by parameter. After the reconstruction is finished, it enqueues th eprocess id wit associated list of gpus.
    Parameters
    ----------
    proc : str
        processing library, chices are cpu, cuda, opencl
    conf_file : str
        configuration file with reconstruction parameters
    datafile : str
        name of file containing data
    dir : str
        parent directory to the <prefix>/results, or results directory
    gpus : list
       a list of gpus that will be used for reconstruction
    r : str
       a string indentifying the module to use for reconstruction
    q : Queue
       a queue that returns tuple of procees id and associated gpu list after the reconstruction process is done
    Returns
    -------
    nothing
    """
    if r == 'g':
        gen_rec.reconstruction(proc, conf_file, datafile, dir, gpus)
    elif r == 'm':
        mult_rec.reconstruction(proc, conf_file, datafile, dir, gpus)
    elif r == 's':
        rec.reconstruction(proc, conf_file, datafile, dir, gpus)
    q.put((os.getpid(), gpus))


def get_gpu_use(devices, no_dir, no_rec, data_shape):
    """
    Determines the use case, available GPUs that match configured devices, and selects the optimal distribution of reconstructions on available devices.
    Parameters
    ----------
    devices : list
        list of configured GPU ids to use for reconstructions. If -1, operating system is assigning it
    no_dir : int
        number of directories to run independent reconstructions
    no_rec : int
        configured number of reconstructions to run in each directory
    data_shape : tuple
        shape of data array, needed to estimate how many reconstructions will fit into available memory
    Returns
    -------
    gpu_use : list
        a list of int indicating number of runs per consecuitive GPUs
    """
    from functools import reduce
				
    if sys.platform == 'darwin':
        # the gpu library is not working on OSX, so run one reconstruction on each GPU
        gpu_load = len(devices) * [1,]
    else:
        # find size of data array
        data_size = reduce((lambda x, y: x * y), data_shape)
        rec_mem_size = data_size / MEM_FACTOR
        gpu_load = ut.get_gpu_load(rec_mem_size, devices)
						
    no_runs = no_dir * no_rec
    gpu_distribution = ut.get_gpu_distribution(no_runs, gpu_load)
    gpu_use = []
    available = reduce((lambda x, y: x + y), gpu_distribution)
    dev_index = 0
    i = 0
    while i < available:
        if gpu_distribution[dev_index] > 0:
            gpu_use.append(devices[dev_index])
            gpu_distribution[dev_index] = gpu_distribution[dev_index] - 1
            i += 1
        dev_index += 1
        dev_index = dev_index % len(devices)
    if no_dir > 1:
        gpu_use = [gpu_use[x:x + no_rec] for x in range(0, len(gpu_use), no_rec)]

    return gpu_use


def manage_reconstruction(proc, experiment_dir, rec_id=None):
    """
    This function starts the interruption discovery process and continues the recontruction processing.
    
    It reads configuration file defined as <experiment_dir>/conf/config_rec.
    If multiple generations are configured, or separate scans are discovered, it will start concurrent reconstructions.
    It creates image.npy file for each successful reconstruction.
    Parameters
    ----------
    proc : str
        processing library, choices are: cpu, cuda, opencl
    experiment_dir : str
        directory where the experiment files are loacted
    rec_id : str
        optional, if given, alternate configuration file will be used for reconstruction, (i.e. <rec_id>_config_rec)
    Returns
    -------
    nothing
    """
    if os.path.exists('stopfile'):
        os.remove('stopfile')
    print('starting reconstruction')

    # the rec_id is a postfix added to config_rec configuration file. If defined, use this configuration.
    conf_dir = os.path.join(experiment_dir, 'conf')
    # convert configuration files if needed
    conv.convert(conf_dir)

    if rec_id is None:
        conf_file = os.path.join(conf_dir, 'config_rec')
    else:
        conf_file = os.path.join(conf_dir, rec_id + '_config_rec')

    # check if file exists
    if not os.path.isfile(conf_file):
        print('no configuration file ' + conf_file + ' found')
        return

    # verify the configuration file
    if not ver.ver_config_rec(conf_file):
        # if not verified, the ver will print message
        return

    try:
        config_map = ut.read_config(conf_file)
        if config_map is None:
            print("can't read configuration file " + conf_file)
            return
    except Exception as e:
        print('Cannot parse configuration file ' + conf_file + ' , check for matching parenthesis and quotations')
        print (str(e))
        return

    # exp_dirs_data list hold pairs of data and directory, where the directory is the root of data/data.tif file, and
    # data is the data.tif file in this directory.
    exp_dirs_data = []
    # experiment may be multi-scan in which case reconstruction will run for each scan
    for dir in os.listdir(experiment_dir):
        if dir.startswith('scan'):
            datafile = os.path.join(experiment_dir, dir, 'data', 'data.tif')
            if os.path.isfile(datafile):
                exp_dirs_data.append((datafile, os.path.join(experiment_dir, dir)))
    # if there are no scan directories, assume it is combined scans experiment
    if len(exp_dirs_data) == 0:
        # in typical scenario data_dir is not configured, and it is defaulted to <experiment_dir>/data
        # the data_dir is ignored in multi-scan scenario
        try:
            data_dir = config_map.data_dir
        except AttributeError:
            data_dir = os.path.join(experiment_dir, 'data')
        if os.path.isfile(os.path.join(data_dir, 'data.tif')):
            exp_dirs_data.append((os.path.join(data_dir, 'data.tif'), experiment_dir))
        elif os.path.isfile(os.path.join(data_dir, 'data.npy')):
            exp_dirs_data.append((os.path.join(data_dir, 'data.npy'), experiment_dir))
    no_runs = len(exp_dirs_data)
    if no_runs == 0:
        print('did not find data.tif nor data.npy file(s). ')
        return
    try:
        generations = config_map.generations
    except:
        generations = 0
    try:
        reconstructions = config_map.reconstructions
    except:
        reconstructions = 1
    device_use = []
    if proc == 'cpu':
        cpu_use = [-1] * reconstructions
        if no_runs > 1:
            for _ in range(no_runs):
                device_use.append(cpu_use)
        else:
            device_use = cpu_use
    else:
        try:
            devices = config_map.device
        except:
            devices = [-1]

        if no_runs * reconstructions > 1:
            if exp_dirs_data[0][0].endswith('tif'):
                data_shape = ut.read_tif(exp_dirs_data[0][0]).shape
            elif exp_dirs_data[0][0].endswith('npy'):
                data_shape = np.load(exp_dirs_data[0][0]).shape
            device_use = get_gpu_use(devices, no_runs, reconstructions, data_shape)
        else:
            device_use = devices

    # start the interrupt process
    interrupt_process = Process(target=interrupt_thread, args=())
    interrupt_process.start()

    if no_runs == 1:
        if len(device_use) == 0:
            device_use = [-1]
        dir_data = exp_dirs_data[0]
        datafile = dir_data[0]
        dir = dir_data[1]
        if generations > 1:
            gen_rec.reconstruction(proc, conf_file, datafile, dir, device_use)
        elif reconstructions > 1:
            mult_rec.reconstruction(proc, conf_file, datafile, dir, device_use)
        else:
            rec.reconstruction(proc, conf_file, datafile, dir, device_use)
    else:
        if len(device_use) == 0:
            device_use = [[-1]]
        else:
            # check if is it worth to use last chunk
            if proc != 'cpu' and len(device_use[0]) > len(device_use[-1]) * 2:
                device_use = device_use[0:-1]
        if generations > 1:
            r = 'g'
        elif reconstructions > 1:
            r = 'm'
        else:
            r = 's'
        q = Queue()
        for gpus in device_use:
            q.put((None, gpus))
        # index keeps track of the multiple directories
        index = 0
        processes = {}
        pr = []
        while index < no_runs:
            pid, gpus = q.get()
            if pid is not None:
                os.kill(pid, signal.SIGKILL)
                del processes[pid]
            datafile = exp_dirs_data[index][0]
            dir = exp_dirs_data[index][1]
            p = Process(target=rec_process, args=(proc, conf_file, datafile, dir, gpus, r, q))
            p.start()
            pr.append(p)
            processes[p.pid] = index
            index += 1

        for p in pr:
            p.join()

        # close the queue
        q.close()

    interrupt_process.terminate()
    print('finished reconstruction')


def main(arg):
    parser = argparse.ArgumentParser()
    parser.add_argument("proc", help="the processor the code will run on, can be 'cpu', 'opencl', or 'cuda'.")
    parser.add_argument("experiment_dir", help="experiment directory.")
    parser.add_argument("--rec_id", help="reconstruction id, a prefix to '_results' directory")
    args = parser.parse_args()
    proc = args.proc
    experiment_dir = args.experiment_dir

    if args.rec_id:
        manage_reconstruction(proc, experiment_dir, args.rec_id)
    else:
        manage_reconstruction(proc, experiment_dir)


if __name__ == "__main__":
    main(sys.argv[1:])

# python run_rec.py opencl experiment_dir
