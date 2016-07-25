#! /usr/bin/python
# TODO: Seperate directory creation from the rest
# TODO: Use JSON to store the basic directory structure
# TODO: Allow custom keywords and ranges. Good luck figuring that out
"""
##########################################
Imports
##########################################
"""

from __future__ import print_function
import numpy as np                       # Linspace
import time                              # Time and date
from itertools import product            # Nested for-loops
import sys                               # Functions to access system functions
import os                                # Functions to access IO of the OS
import shutil                            # High-level file manegement
import platform                          # Information about the platform
import multiprocessing                   # Multiprocessing
import logging                           # Logging progress from the processes
import copy                              # For deepcopy
import traceback                         # To log tracebacks
import subprocess                        # More flexible os.system
from mpi4py import MPI                   # For supercomputing
from tools import *
from input_reader import *

"""
##########################################
Global Variables
##########################################
"""
Z_nr = {'H': '001',  'He': '002', 'Li': '003',  'Be': '004', 'B': '005',   'C': '006',  'N': '007',   'O': '008',  'F': '009',  'Ne': '010',
        'Na': '011', 'Mg': '012', 'Al': '013',  'Si': '014', 'P': '015',   'S': '016',  'Cl': '017',  'Ar': '018', 'K': '019',  'Ca': '020',
        'Sc': '021', 'Ti': '022', 'V': '023',   'Cr': '024', 'Mn': '025',  'Fe': '026', 'Co': '027',  'Ni': '028', 'Cu': '029', 'Zn': '030',
        'Ga': '031', 'Ge': '032', 'As': '033',  'Se': '034', 'Br': '035',  'Kr': '036', 'Rb': '037',  'Sr': '038', 'Y': '039',  'Zr': '040',
        'Nb': '041', 'Mo': '042', 'Tc': '043',  'Ru': '044', 'Rh': '045',  'Pd': '046', 'Ag': '047',  'Cd': '048', 'In': '049', 'Sn': '050',
        'Sb': '051', 'Te': '052', 'I': '053',   'Xe': '054', 'Cs': '055',  'Ba': '056', 'La': '057',  'Ce': '058', 'Pr': '059', 'Nd': '060',
        'Pm': '061', 'Sm': '062', 'Eu': '063',  'Gd': '064', 'Tb': '065',  'Dy': '066', 'Ho': '067',  'Er': '068', 'Tm': '069', 'Yb': '070',
        'Lu': '071', 'Hf': '072', 'Ta': '073',  'W': '074',  'Re': '075',  'Os': '076', 'Ir': '077',  'Pt': '078', 'Au': '079', 'Hg': '080',
        'Tl': '081', 'Pb': '082', 'Bi': '083',  'Po': '084', 'At': '085',  'Rn': '086', 'Fr': '087',  'Ra': '088', 'Ac': '089', 'Th': '090',
        'Pa': '091', 'U': '092',  'Np': '093',  'Pu': '094', 'Am': '095',  'Cm': '096', 'Bk': '097',  'Cf': '098', 'Es': '099', 'Fm': '100',
        'Md': '101', 'No': '102', 'Lr': '103',  'Rf': '104', 'Db': '105',  'Sg': '106', 'Bh': '107',  'Hs': '108', 'Mt': '109', 'Ds': '110',
        'Rg': '111', 'Cn': '112', 'Uut': '113', 'Fl': '114', 'Uup': '115', 'Lv': '116', 'Uus': '117', 'Uuo': '118'}

"""
###########################################
Functions
###########################################
"""

"""
##########################################
Classes
##########################################
"""

class Manager:
    """ Runs the simulations """

    def __init__(self, options, args):
        self.options = options  # Arguments read from file
        self.args = args        # Arguments read from terminal
        self.use_MPI = size > 1
        if self.use_MPI and self.args.processes > 0:
            print("Multiprocessing can not be used with MPI")
            comm.Abort()
        self.mpisize = size

        # sys.excepthook is what deals with an unhandled exception
        sys.excepthook = self.excepthook

        for n in range(1, self.mpisize):
            comm.send(self.options, dest=n, tag=1)

    def __enter__(self, options, args):
        self.__init__(self, options, args)

    def __exit__(self, exc_type, exc_value, traceback):
        """ Shut down the children when exiting """
        for rank in range(self.mpisize):
            comm.send("stop", dest=rank)

    def init_logger(self):
        """ Set up logging
        This is the best tool to handle information that should either be
        printed to the terminal or written to a file. All of the information
        from both normal and abnormal execution is written to both the terminal
        and to the log file (default name is talys.log), but debugging
        information is also written to the log file. To ease troubleshooting,
        error messages is also written to the error file (default name is
        error.log).
        """

        # use a multiprocessing-safe logger if --processes is set
        if self.args.processes > 0:
            self.logger = multiprocessing.get_logger()
        else:
            self.logger = logging.getLogger()

        # create and add a filter to suppress multiprocessing information
        class NoMultiProcessingFilter(logging.Filter):
            def filter(self, record):
                return not "process" in record.getMessage()

        self.logger.addFilter(NoMultiProcessingFilter())

        # File Handler - writes log messages to log file
        log_handle = logging.FileHandler(
            os.path.join(self.root_directory, self.args.lfilename))
        log_handle.setLevel(self.args.log)

        # File Handler - writes error messages to error file
        error_handle = logging.FileHandler(
            os.path.join(self.root_directory, self.args.efilename))
        error_handle.setLevel(logging.ERROR)

        # Console handler - writes log messages to the console
        console_handle = logging.StreamHandler()
        console_handle.setLevel(self.args.verbosity)

        # Formatter - formates the input
        # something is really buggy here, but by a miracle, it got fixed
        # do not touch this
        formatter = logging.Formatter('%(asctime)s - %(processName)-12s -  %(levelname)-8s - %(message)s')
        log_handle.setFormatter(formatter)
        console_handle.setFormatter(formatter)
        error_handle.setFormatter(formatter)

        # connect the handlers to the actual logging
        self.logger.addHandler(log_handle)
        self.logger.addHandler(console_handle)
        self.logger.addHandler(error_handle)

        # for debugging purposes
        if self.args.processes > 0:
            self.logger.debug(multiprocessing.current_process().pid)
        if self.use_MPI:
            self.logger.warning("Only rank 0 can use logging")

    def excepthook(self, ex_cls, ex, tb):
        """ Replace the default excepthook
        the excepthook is called when the script experiences an exception.
        In order to log the traceback and ensure termination of the child
        processes, this excepthook replaces the default one
        """
        # log the traceback in a readable format
        self.logger.critical(''.join(traceback.format_tb(tb)))
        # log a short summary of the exception
        self.logger.critical('{0}: {1}'.format(ex_cls, ex))
        # kill the kids
        for p in multiprocessing.active_children():
            p.terminate()
        sys.exit()

    def make_info_file(self):
        """ Create the  file and energy file """
        padding_size = 20
        # create file

        outfile = open(os.path.join(self.root_directory, "Information.txt"), 'w')
        input = self.options

        # write date, time and input  to file
        outfile.write('TALYS-calculations')

        outfile.write('\n{:<{}s} {}'.format(
            "Date:", padding_size, time.strftime('%d %B %Y')))
        outfile.write('\n{:<{}s} {}'.format(
            "Time:", padding_size, time.strftime('%H:%M:%S-%Z')))

        # write system information
        outfile.write('\n{:<{}s} {}'.format(
            "Platform:", padding_size, platform.platform()))
        outfile.write('\n{:<{}s} {}'.format(
            "Python version:", padding_size, platform.python_version()))

        # write energy information
        outfile.write('\n\n{:<{}s} {}'.format(
            "name of energy file:", padding_size, input['energy']))
        outfile.write('\n{:<{}s} {}'.format(
            "energy min:", padding_size, input['E1']))
        outfile.write('\n{:<{}s} {}'.format(
            "energy max:", padding_size, input['E2']))
        outfile.write('\n{:<{}s} {}'.format(
            "number of energies:", padding_size, input['N']))

        outfile.write('\n\n{:<{}s} {}'.format(
            "name of input file:", padding_size, input['input_file']))
        outfile.write('\n{:<{}s} {}'.format(
            "name of output file:", padding_size, input['output_file']))
        outfile.write('\n\nVariable input:')

        for value, key in input.keywords.iteritems():
            outfile.write('\n{:<{}s} {}' .format(
                value + ':',  padding_size, key))

        outfile.write('\n\nEnergies: \n')

        # create energy input
        energies = np.linspace(float(self.options['E1']),
                               float(self.options['E2']),
                               float(self.options['N']))
        # outfile named energy_file
        outfile_energy = open(os.path.join(self.root_directory, self.options['energy'][0]), 'w')
        # write energies to energy_file and file in one column
        for Ei in energies:
            # write energies to file in column
            outfile_energy.write('%.2E \n' % Ei)
            # write energies to  file in one column
            outfile.write('%.2E \n' % Ei)

        outfile_energy.close()
        outfile.close()

    def make_input_file(self, keywords, directories):
        keywords = copy.deepcopy(keywords)

        # pop out the keywords that shouldn't be written twice
        projectile = keywords.pop('projectile')
        mass = keywords.pop('mass')
        element = keywords.pop("element")
        energy = keywords.pop('energy')

        # open the file and begin writing
        outfile_input = open(os.path.join(
            directories["rest_directory"],
            self.options["input_file"]), 'w')
        # This shows the reaction taking place, e.g 159Eu(n,g)160Eu
        reaction_line = '{}{}({},g){}{}'.format(mass, element, projectile,
                                                int(mass)+1, element)
        outfile_input.write('########################## \n')
        outfile_input.write('##   TALYS input file   ## \n')
        outfile_input.write('##{:^{}}## \n'.format(reaction_line, 22))
        outfile_input.write('########################## \n \n')
        outfile_input.write('# All keywords are explained in README. \n \n')

        outfile_input.write('element {} \n'.format(element))
        outfile_input.write('projectile {} \n'.format(projectile))
        outfile_input.write('mass {} \n'.format(mass))
        outfile_input.write('energy {} \n \n'.format(energy))

        # Write the keyword and corresponding value
        for key, value in keywords.iteritems():
            outfile_input.write('{} {} \n'.format(key, str(value)))

        # Bad things happen if the file isn't closed
        outfile_input.close()

        # Copy energy file  to isotope directory
        src_energy_new = os.path.join(
            self.root_directory, energy)
        # dst input file > variable directory
        dst_energy_input = directories["rest_directory"]

        # copy energy file to variable directory
        shutil.copy(src_energy_new, dst_energy_input)

    def run(self):
        """ Runs the simulations """
        start = time.time()
        # do a deepcopy to prevent multiprocessing mixing
        keywords = copy.deepcopy(self.options.keywords)

        # directories keep the values of each file path and directory path
        # to 1) make it possible to add to it 2) prevent subprocesses from
        # adding and removing from eachothers directories 3) make it easier
        # to send names and paths through functions
        directories = {}

        # mkdir: > TALYS-calculations-date-time
        self.root_directory = 'TALYS-calculations-{}-{}'.format(
            time.strftime('%y%m%d'), time.strftime('%H%M%S'))
        directories["root_directory"] = self.root_directory
        mkdir(self.root_directory)

        # initialize and start the logging
        self.init_logger()

        # make the info file. If it fails, quit the script
        self.make_info_file()

        # mkdir: > TALYS-calculations-date-time/original_data
        directories["original_data"] = os.path.join(
            directories["root_directory"], "original_data")
        mkdir(directories["original_data"])

        # mkdir: > TALYS-calculations-date-time/results_data
        directories["results_data"] = os.path.join(
            directories["root_directory"], "results_data")
        mkdir(directories["results_data"])

        # change to "current" directories
        directories["current_orig"] = directories["original_data"]
        directories["current_res"] = directories["results_data"]
        # key = self.keygen()
        # fmt = KeyFormatter()
        # value = {
        #    "{element}":"Pr",
        #    "{mass}":{"Pr":128}
#}
 #       fmt.format("{mass[{mass}]}", **value)
  #      sys.exit()
        #self.run_deeper(keywords, directories, key)
        for element in self.options["element"]:
            keywords["element"] = element
            self.run_element(element, keywords, directories)

        elapsed = time.strftime("%H:%M:%S", time.localtime(time.time() - start))
        self.logger("Total elapsed time: %s", elapsed)

    def keygen(self):
        #TODO: Add Z_nr[]
        iterator = [
            {"element": "{element}"},
            {"mass": "{mass[{element}]}{element}"},
            {"rest": ""},
        ]
        for item in iterator:
            yield (item.keys()[0], item.values()[0])

    def run_deeper(self, keywords, directories, key):
        # deepcopy the mutable variables to prevent processing mixup
        keywords = copy.deepcopy(keywords)
        directories = copy.deepcopy(directories)
        raw_input()
        for name, style in key:
            print(name, style)
            print(style.format(**keywords))
            if name == "rest":
                self.run_rest(keywords, directories)
            else:
                new_keywords = copy.deepcopy(keywords)
                for keyword in keywords[name]:
                    print("Current keyword", keyword)
                    if isinstance(keyword, (dict)):
                        new_keywords[name] = new_keywords[name][new_keywords["prev_keywords"]]
                    else:
                        new_keywords[name] = keyword
                    new_keywords["prev_keyword"] = keyword
                    directories["current_orig"] = os.path.join(
                        directories["current_orig"], style.format(**new_keywords))
                    directories["current_res"] = os.path.join(
                        directories["current_res"], style.format(**new_keywords))
                    mkdir(directories["current_orig"])
                    mkdir(directories["current_res"])
                    self.run_deeper(new_keywords, directories, key)

    def run_element(self, element, keywords, directories):
        """ Manages the element-option """

        # deepcopy the mutable variables to prevent processing mixup
        keywords = copy.deepcopy(keywords)
        directories = copy.deepcopy(directories)

        # mkdir: > TALYS-calculations-date-time/original_data/astro-a/ZZ-X
        directories["element_original"] = os.path.join(
            directories["current_orig"], '{}{}'.format(Z_nr[element], element))
        mkdir(directories["element_original"])

        # mkdir: > TALYS-calculations-date-time/result_data/astro-a/ZZ-X
        directories["element_results"] = os.path.join(
            directories["current_res"], "{}{}".format(Z_nr[element], element))
        mkdir(directories["element_results"])

        # change the "current" directory
        directories["current_orig"] = directories["element_original"]
        directories["current_res"] = directories["element_results"]
        for mass in self.options['mass'][element]:
            keywords['mass'] = mass
            self.run_mass(mass, keywords, directories)

    def run_mass(self, mass, keywords, directories):
        """ Manages the mass-option """
        # deepcopy the mutable variables to prevent processing mixup
        keywords = copy.deepcopy(keywords)
        directories = copy.deepcopy(directories)

        # mkdir: > TALYS-calculations-date-time/original_data/astro-a/ZZ-X/isotope
        directories["isotope_original"] = os.path.join(
            directories["current_orig"], "{}{}".format(keywords["mass"], keywords["element"]))
        mkdir(directories["isotope_original"])

        # mkdir: > TALYS-calculations-date-time/result_data/astro-a/ZZ-X/isotope
        directories["isotope_results"] = os.path.join(
            directories["current_res"], "{}{}".format(keywords["mass"], keywords["element"]))
        mkdir(directories["isotope_results"])

        # change to "current" directory
        directories["current_orig"] = directories["isotope_original"]
        directories["current_res"] = directories["isotope_results"]

        # handle the rest of the keywords
        self.run_rest(keywords, directories)

    def run_rest(self, keywords, directories):
        """ Creates the name of the final directory and calls self.run_talys()
        The format is keyword1value-keyword2value-...-conditional1name -
        conditional1value-conditional2name-conditional2value-...
        in alphabetical order"""

        # deepcopy the mutable variables to prevent processing mixup
        keywords = copy.deepcopy(keywords)
        directories = copy.deepcopy(directories)

        keys = []
        values = []
        talys_keywords = {}

        # put the keys in alphabetical order
        sorted_keys = keywords.keys()
        sorted_keys.sort()
        for key in sorted_keys:
            # only use keywords that vary, and astro
            if (len(self.options[key]) > 1
                and key != "element"
                and key != "mass"
            )   or key == "astro":
                # the next two lists are in alphabetical order, and
                # corresponding key-value pair have the same index
                keys.append(key)
                values.append(keywords[key])
            else:
                talys_keywords[key] = keywords[key]
        # 1) append the conditional names to the keywords, since they
        # are the one to be chosen from. This is undone in 2)
        for condition in self.options.conditionals:
            values.append(condition.keys())

        # the queue is used to track the completed subprocesses.
        # a queue is used since it is multiprocessing-safe
        self.talys_queue = multiprocessing.Queue()
        # talys_jobs contains the subprocesses
        talys_jobs = []
        self.counter = multiprocessing.Value('i', 0)
        self.counter_max = 0
        for n in product(*values):
            self.counter_max += 1

        current_rank = np.array([1])
        send_to_rank = np.array([1])
        for value in product(*values):
            # 2) splits the result back into keywords and conditions
            keywordvals = value[:len(keys)]
            conditionkeys = value[len(keys):]

            # name the directory according to the alphabetical order
            # of the keywords
            name = ''
            for i in range(len(keywordvals)):
                # add to the name
                name = "{}-{}".format(name, keywordvals[i])
                # add the now one-option keyword to talys_keywords
                talys_keywords[keys[i]] = keywordvals[i]

            #remove the unecessary -
            name = name[1:]

            # furthermore, name the directory accoring to the chosen condition
            for key in conditionkeys:
                value = self.options.get_condition_val(key)
                name = "{}-{}-{}".format(name, key, value)
                talys_keywords[key] = value

            keywords["name"] = name
            # make all values to non-lists
            for key, val in talys_keywords.iteritems():
                if isinstance(val, (list, tuple)):
                    talys_keywords[key] = val[0]

            # make the directories
            directories["rest_directory"] = os.path.join(
                directories["current_orig"], name)
            mkdir(directories["rest_directory"])

            # make input file
            try:
                self.make_input_file(talys_keywords, directories)
            except Exception as exc:
                # no biggie. Just print an error and move on
                self.logger.error("An error occured with %s: %s", name, exc)
                continue

            # run TALYS
            """ Use multiprocessing on each run of talys"""
            # if --processes is not set, jump over this
            if self.args.processes > 0:
                # only pause if the limit set by --processes is reached
                if len(talys_jobs) >= self.args.processes:
                    """
                    Use the set number of processes. Wait for available
                    Gets blocked until something is put on the queue, i.e.
                    one of the subprocesses has finished
                    """
                    self.logger.debug("Waiting for available process")
                    # (pid = process identification)
                    pid = self.talys_queue.get()

                    # to prevent any fuckups, wait for the process to
                    # finished if, by any chance, it hasn't.
                    # it looks like this happens once in a while
                    time.sleep(1)
                    for process in talys_jobs:
                        if process.pid == pid:
                            if process.is_alive():
                                self.logger.warn("%s was not terminated", pid)
                                process.join()
                                # remove it from the list and put a new on
                            self.logger.debug("Removing %s from list", pid)
                            talys_jobs.remove(process)
                            break

                # set up the subprocess
                talys_job = multiprocessing.Process(
                    target=self.run_talys, args=(keywords, directories, ))
                # keep a reference so it can be shut down
                talys_jobs.append(talys_job)
                # and let it loose into the wild!
                talys_job.start()
            elif self.use_MPI:
                if current_rank >= self.mpisize:
                    self.logger.debug("Waiting for available process")
                    comm.Recv(send_to_rank, source=MPI.ANY_SOURCE)
                    print(send_to_rank)
                    current_rank -= 1
                comm.send((keywords, directories), dest=send_to_rank[0])
                current_rank[0] += 1
                send_to_rank = current_rank
            else:
                # no multiprocessing
                self.run_talys(keywords, directories)

        # Wait for all of the talys_jobs to complete
        for talys_job in talys_jobs:
            talys_job.join()

    def run_talys(self, keywords, directories):
        """ Runs TALYS """
        # deepcopy the directories list to prevent multiprocessing mixup
        directories = copy.deepcopy(directories)
        directories["current_orig"] = directories["rest_directory"]
        # actually run TALYS and time its execution
        start = time.time()
        with Cd(directories["current_orig"]):
            process = subprocess.call('talys <{}> {}'.format(
                self.options["input_file"],
                self.options["output_file"]),
                                      # do not send signals to the subprocess
                                      preexec_fn=os.setpgrp,
                                      # spawn a shell
                                      shell=True,
                                      # get both stdout and stderr
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT,
                                      # don't know
                                      close_fds=True)

        elapsed = time.strftime("%M:%S", time.localtime(time.time() - start))
        info = "{mass}{element}-{name}".format(**keywords)
        if not self.use_MPI:
            self.counter.value += 1
            self.logger.info("(%s/%s) Execution time: %s by %s", self.counter.value,
                             self.counter_max, elapsed, info)
            # the filesize of output_file is an indicator of whether the execution
            # was successfull or not
            path = os.path.join(
                directories["current_orig"], self.options["output_file"])
            if os.path.getsize(path) < 600:
                # execution failed. Open the file and log the output
                with open(path, "r") as output_file:
                    msg = ''.join(output_file.readlines()).rstrip()
                self.logger.error(msg[1:])
        else:
            print("Execution time: {} by {}".format(elapsed, info))

        # move result file to
        # TALYS-calculations-date-time/original_data/astro-a/ZZ-X/isotope
        # try:
        #     shutil.copy(os.path.join(directories["current_orig"], "astrorate.tot"),
        #                 os.path.join(directories["current_res"], "{}-astrorate.tot".format(keywords["name"])))
        # except Exception as exc:
        #     # if this happens, the cause is always that TALYS hasn't run
        #     # therefore, print the STDOUT/STDERR from talys
        #     #error = str(process.stdout.read()).rstrip()
        #     #error = error if error else exc
        #     self.logger.error("An error occured while copying the result: %s - %s",
        #                       process, exc)

        # tell the parent process that the child has finnished
        # the purpose of this is to let the next process begin
        if not self.use_MPI:
            self.logger.debug("{} is terminating".format(
                multiprocessing.current_process().pid))
            self.talys_queue.put(multiprocessing.current_process().pid)


# For MPI
class ChildRunner(Manager):
    # Remove Manager's init
    def __init__(self, rank):
        self.rank = rank
        self.use_MPI = True
        self.options = comm.recv(source=0, tag=1)
        self.wait_for_root()

    def wait_for_root(self):
        while True:
            try:
                keywords, directories = comm.recv(source=0)
                if "stop" in directories:
                    break
                self.run_talys(keywords, directories)
            finally:
                comm.Send(np.array([self.rank]), dest=0)

# Keep the script from running if imported as a module
if __name__ == "__main__":
    # Set up MPI. This must always be first
    # The almighty communicator. Communicates messages between the nodes in a
    # supercomputing cluster
    comm = MPI.COMM_WORLD
    # The rank is the current process' ID
    rank = comm.Get_rank()
    # Size is the number of processes
    size = comm.Get_size()

    # Only the root process, 0, shall create the directories
    if rank == 0:
        # Handle the arguments from terminal
        args = get_args()

        # Set up  logging
        try:  # Python 2.7+
            from logging import NullHandler
        except ImportError:
            class NullHandler(logging.Handler):
                def emit(self, record):
                    pass

        # Had a bug, this fixed it. It should't have, but it did. Leave it be
        logging.basicConfig(level=logging.DEBUG, filename=args.lfilename,
                            filemode="w", format="%(asctime)s - %(processName)-12s -  %(levelname)-8s - %(message)s")
        logging.getLogger("__name__").addHandler(NullHandler())

        # Get the options
        options = Json_reader(args.input_filename)

        # Create an instance of Manager to run the simulations
        with Manager(options=options, args=args) as simulations:
            simulations.run()
    else:
        # The other processes run TALYS, but must wait for root
        ChildRunner(rank)

