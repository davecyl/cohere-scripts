import sys
import argparse
import os


config_file_names = ['config', 'config_prep', 'config_rec', 'config_disp', 'config_data']

# Map file of before/after keys to remap

config_map = {'beamline': 'beamline', 'specfile': 'specfile'}
config_prep_map = {'darkfile': 'darkfield_filename', 'whitefile': 'whitefield_filename'}
config_rec_map = {'samples': 'reconstructions', 'amp_support_trigger': 'shrink_wrap_trigger',
                  'support_type': 'shrink_wrap_type', 'hio_beta' : 'beta', 'shrink_wrap_threshold' : 'support_threshold',
                  'shrink_wrap_gauss_sigma' : 'support_sigma', 'initial_support_area' : 'support_area',
                  'pc_trigger' : 'pcdi_trigger', 'pc_type' : 'partial_coherence_type',
                  'pc_LUCY_iterations' : 'partial_coherence_iteration_num', 'pc_normalize' : 'partial_coherence_normalize',
                  'pc_LUCY_kernel' : 'partial_coherence_roi', 'phm_phase_min' : 'phase_min', 'phm_phase_max' : 'phase_max',
                  'lowpass_filter_sw_sigma_range' : 'iter_res_sigma_range', 'lowpass_filter_range' : 'iter_res_det_range',
                  'ga_generations' : 'generations', 'ga_shrink_wrap_thresholds' : 'ga_support_thresholds',
                  'ga_shrink_wrap_gauss_sigmas' : 'ga_support_sigmas', 'ga_lowpass_filter_sigmas' : 'ga_low_resolution_sigmas',
                  'ga_gen_pc_start' : 'gen_pcdi_start'}
config_disp_map = {'arm': 'detdist', 'dth': 'theta'}
config_data_map = {'aliens': 'aliens', 'intensity_threshold' : 'amp_threshold'}

beamlinedefaultvalue = ' "aps_34idc"'

# Tuple contains a list of map files to use

config_map_tuple = (config_map, config_prep_map, config_rec_map, config_disp_map, config_data_map)

# Prior to any change make a backup of the original file


def versionfile(file_spec, vtype='copy'):
    # Prior to any change make a backup of the original file
    import os
    import shutil

    if os.path.isfile(file_spec):
        # or, do other error checking:
        if vtype not in ('copy', 'rename'):
            vtype = 'copy'

        # Determine root filename so the extension doesn't get longer
        n, e = os.path.splitext(file_spec)
        # Is e an integer?
        try:
            num = int(e)
            root = n
        except ValueError:
            root = file_spec + "_backup"
            shutil.copy(file_spec, root)
#            print("Backing up the file", file_spec, " to the file", root, "\n")
            return 0


def returnconfigdictionary(cfile, startdir):
    """
    This function takes a config file name and creates a dictionary of all the parameters defined in the config
    file using the = to split key,value pairs.
    There is a special case where values can be enclosed in () with a line for each value.
    Parameters
    ----------
    cfile : str
        configuration file name
    startdir : str
        a directory with configuration files to be converted
    Returns
    -------
    currentdic : dict
        a dictionary with the configuration parameters
    """
    param = ''
    value = ''
    extend = False
    currentdic = {}

    # Check if file exists, if it does make a backup copy of file with the new name config_backup
    newpath = os.path.join(startdir, cfile)
    if os.path.exists(newpath):
        backupfile = cfile + "_backup"
        versionfile(newpath)
    else:
#        print('The file', cfile, ' does not exist')
        return currentdic
    # input = open(cfile, 'r')
    input = open(newpath, 'r')
    str = input.readline()
    while str:
        # Ignore comment lines and move along
        str = str.rstrip()
        if '//' in str:
            str = input.readline()
            continue
        elif extend == False:
            # Test if = is in the string otherwise skip this line, if = in line split on = only if this is not an
            # extended string seperated by the () brackets
            if "=" not in str:
#                print("strange string in config=", str)
                str = input.readline()
                continue
            param, value = str.split('=')
            param = param.rstrip()
            currentdic[param] = value
        else:
            #       in the extended string area capture the string and check if at begining or end
            value = value + str
        if value == " (" or value == " [":
            extend = True
        elif str == ")" or str == "]":
            #       At the end of extended string push string into dictionary and end loop
            currentdic[param] = value
            extend = False
        str = input.readline()
    input.close()
    return currentdic


def convert(startdir):
    """
    This script will convert old config files to the newer format using the following critera
    Config file
    Move specfile from config_prep
    Add beamline
    Add/replace converter_ver
    config_prep
    change darkfile to darkfield_filename
    change whitefile to whitefield_filename
    config_rec
    changed samples to reconstructions
    changed amp_support_trigger to shrink_wrap_trigger
    changed support_type to shrink_wrap_type
    +
    config_disp
    changed arm to detdist
    changed dth to theta
    The path where the config files are located is one of the parameters passed to the script via the -p variable,
    new files and backup files are written back to the same path as supplied.
    Prior to any work, a backup of the original file is made to file_backup
    Newly mapped files then replace the original file with the new parameters which are then mapped to the original
    values.
    How it works: Each config file in the list config_file_names is read in and a dictionary of the file parameters
    (keys) is assigned a value. All config files are read into one large
    dictionary of dictionaries. Each config file key,value pairs is then compared with the map file associated with that
    config file using the config_map_tuple to steer the mapping.
    If a match is found the value of the key replaces the original key. The remapped key,value pair is then written out
    to the same file name thereby replacing the original file.
    There are special cases that needed to be added to this general mapping strategy, If the config file had the
    "beamline" parameter already defined then keep its value if not then I
    picked a default value of aps_sec34id-c. If the specfile parameter was found in config_prep it was moved over to the
    config file.
    All non-relevant data in the files are stripped out including spaces and comments.
    If an aliens parameter is found id the config_data
    file it is tested to see if it is a file or a set of coordinates and the alien_alg is set to the correct type.
    Parameters
    ----------
    startdir : str
        a directory with configuration files to be converted
    Returns
    -------
    nothing
    """
    # First check to see if directory exists, if not then exit
    if not os.path.exists(startdir):
        # there is nothing to convert
        return

    # Now go into the content of each config  file and create a dictionary of line items to work with

    allconfigdata = {}

    for cfile in config_file_names:
        thisdic = returnconfigdictionary(cfile, startdir)

    # Create a dictionary of dictionaries to work with

        allconfigdata[cfile] = thisdic

    # Now work of manipulating the config file data

    # Use map file to see what items need to change

    # Display the before data

    # for keydata in allconfigdata.keys():
    #    print("The previous parameter names and values of config file", keydata, "are\n", allconfigdata[keydata], "\n")

    # Use the map file to determine what parameters need to be changed.
    # if the key is found then do the remapp, if not then skip.

    map_index = 0
    for cfile in config_file_names:
        mappingfile = config_map_tuple[map_index]
    # Check if key is in the dictionary for this config file

        for (k, v) in mappingfile.items():
            if k in allconfigdata[cfile].keys():
                # Key is in the dictionary, replace with new value
                holdingvalue = allconfigdata[cfile].pop(k)
                allconfigdata[cfile][v] = holdingvalue
    #            print("The value of", k, "has been changed to", v, "and the value is", holdingvalue)
            else:
                # Key is not in the dictionary, do nothing
                continue
        map_index = map_index + 1

        # Some special cases if beamline has no value then it was never defined so set it to the default
        # if specfile is in config_prep then remove it a add it to config
        # if the config_data file has the older aliens format of coordinates/file then update to new layout

        if cfile == 'config':
            if 'beamline' in allconfigdata[cfile].keys():
                beamlinevalue = allconfigdata[cfile]['beamline']
    #            print("beamline value is", beamlinevalue)
            else:
                beamlinevalue = beamlinedefaultvalue
    #            print("setting default beamline value")
            allconfigdata[cfile]['beamline'] = beamlinevalue
            if 'converter_ver' in allconfigdata[cfile]:
                allconfigdata[cfile].pop('converter_ver')   # remove converter version
        # if specfile is in config_prep move it to config with the same value
        elif cfile == 'config_prep':
            if 'specfile' in allconfigdata[cfile].keys():
                savedspecfilevalue = allconfigdata[cfile].pop('specfile')
                allconfigdata['config']['specfile'] = savedspecfilevalue
    # Look to see if aliens is set and if it is a directory or a block of coordinates
        elif cfile == 'config_data':
            # if alien_alg is defined then this is current and no change is needed.
            if 'alien_alg' in allconfigdata[cfile].keys():
                continue
            elif 'aliens' in allconfigdata[cfile].keys():
                savedAlien = allconfigdata[cfile].pop('aliens')
                if "(" in savedAlien:
                    allconfigdata[cfile]['alien_alg'] = ' "block_aliens"'
                    allconfigdata[cfile]['aliens'] = savedAlien
                else:
                    allconfigdata[cfile]['alien_alg'] = ' "alien_file"'
                    allconfigdata[cfile]['alien_file'] = savedAlien


    # Write the data out to the same-named file

    for k in allconfigdata.keys():
    #    print("The new parameter and values for the config file", k, "are\n", allconfigdata[k], "\n")

    # If config file dictionary is empty then nothing to write

        if bool(allconfigdata[k]):
            newfilename = k
            writepath = os.path.join(startdir, newfilename)
            fileobj = open(writepath, 'w')
            for subkey in allconfigdata[k].keys():
                string2write = subkey + " =" + allconfigdata[k][subkey] + '\n'
                fileobj.write(string2write)
            fileobj.close()
        else:
            continue


def main(arg):
    parser = argparse.ArgumentParser()
    parser.add_argument("conv_dir", help="path to directory with configuration files that will be converted")
    args = parser.parse_args()
    convert(args.conv_dir)


if __name__ == "__main__":
    main(sys.argv[1:])