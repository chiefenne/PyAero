import copy
import time

import numpy as np
import pandas as pd
import math
import datetime as dt
import re
import os
import shutil
import subprocess
from multiprocessing import Queue, Process

class SU2instance:
    """
    This class represents an SU2 instance (or, if run with parallel processing, an MPIexec instance)
    Functionality includes:
    - modifying a "master" configuration and storing the modified copy as "tmp.cfg" for the desired case ("sample")
    - executing SU2 (with multiprocessing support)
    - reading the history file. (this also puts the history into a queue object which can be accessed from outside)
    - checking whether the simulation has finished by itself (i.e., SU2 has decided that it converged)
    - checking whether the simulation is "oscillating" (i.e., SU2 keeps iterating over time with a variation too large
        to satisfy the convergence criteria)  - this has not been tested recently
    """
    def __init__(self, sample, paths, restart_from=False, deviations={}, min_iter=300, k=0, dynamic_monitor_var="CD", settings={}):
        # initing attributes
        self.process = None
        self.dyn_sol_k1 = None  # iteration number of the first solution of a dynamic simulation (e.g. min cD)
        self.dyn_sol_k2 = None  # iteration number of the first solution of a dynamic simulation (e.g. max cD)
        self.history = None
        self.settings = settings
        self.restart_from = restart_from
        self.shift_max = int(settings.get('shift_max', 50))
        self.dyn_stab_length = int(settings.get('n_iter_convergence', 50))
        self.max_trend_diff = 2e-4
        self.cauchy_iter = int(settings.get('n_iter_convergence', 50))
        self.p_plot = None
        self.maxlen = int(settings.get("restart_file_freq", 100))  # this will raise an error if it does not exist, but that's good  # 2025-06-28: changed to default
        self.flowfield_freq = int(settings.get("flowfield_freq", 100))
        if self.settings.get('live_plot', True):
            self.queue = Queue()
            self.queue.cancel_join_thread()  # avoid blocking of process
        # initing object
        for location in ['work_subdir', 'template_dir', 'su2_executable']:  # out_dir
            if location not in list(paths.keys()):
                raise ValueError(f"At least one path ({location}) is not defined!")
        self.paths = paths
        self.cfg = os.path.join(self.paths['work_subdir'], 'tmp.cfg')
        self.logfile = os.path.join(self.paths["work_subdir"], "stdout.log")
        self.past_history_files = set()
        self.past_history = pd.DataFrame()
        self.past_history = self.get_history()
        self.dyn_monitor_var = f'"{dynamic_monitor_var}"'
        self.deviations = deviations
        self.deviations.update({'AOA': sample['aoa'] - np.arctan2(sample['y_TE'], 1) * 180 / np.pi,  # TODO: check sign!!
                                'MACH_NUMBER': sample['Ma'],
                                'REYNOLDS_NUMBER': sample['Re'],
                                'OUTPUT_WRT_FREQ': f'({self.maxlen}, {self.flowfield_freq})',
                                'CONV_WINDOW_CAUCHY_ELEMS': self.cauchy_iter})

        if self.restart_from > 0:
            self.deviations.update({'RESTART_SOL': 'YES',
                                    'RESTART_ITER': self.restart_from+1,
                                    'WINDOW_START_ITER': max(min_iter, self.restart_from+1)})  # TODO: check for off-by-one
        self.prepare()

    def prepare(self, template=None):  # modify config file
        if template is None:
            template = os.path.join(self.paths['template_dir'], 'su2_master.cfg')
        with open(template) as f_src:
            with open(self.cfg, "w") as f_dest:
                while True:
                    try:
                        line = next(f_src)
                        f_dest.write(self._modify_cfg(line))
                    except StopIteration:
                        break

    def _modify_cfg(self, line):
        for parameter, value in self.deviations.items():
            pattern = "^"+parameter+"= "
            match = re.search(pattern, line)
            if match:
                return f'{parameter}= {value}\n'
        return line

    def run(self, cores=1):
        self.exec(self.paths["su2_executable"], self.cfg, n_cores=cores)

    def exec(self, executable, *args, **kwargs):
        n_cores = kwargs.get('n_cores', 1)
        if n_cores == 1:
            with open(self.logfile, "w") as outfile:
                self.process = subprocess.Popen([executable, *args], cwd=self.paths["work_subdir"], stdout=outfile)  # Popen: , stdout=subprocess.PIPE, shell=True, preexec_fn=os.setsid)
        else:
            with open(self.logfile, "w") as outfile:
                self.process = subprocess.Popen(['mpiexec', '-n', str(n_cores), executable, *args], cwd=self.paths["work_subdir"], stdout=outfile)  # Popen: , stdout=subprocess.PIPE, shell=True, preexec_fn=os.setsid)
        # print("SU2 finished.")

    def kill(self):
        # os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
        pass

    @staticmethod
    def get_restarts(workdir):
        restarts = []
        for root, dirs, files in os.walk(workdir):
            for file in files:
                match = re.search("restart_flow_(\d{5}).dat", file)
                if match:
                    restarts.append(int(match.groups()[0]))
        for i in range(len(restarts)-1):
            if restarts[-1-i] == restarts[-2-i]+1:
                return restarts[-1-i]
        return 0

    def get_history(self):
        data_by_files = {}
        for root, dirs, files in os.walk(self.paths['work_subdir']):  # su2 creates a new history file when continuing from a restart-file
            for file in files:
                ffull = os.path.join(root, file)
                if 'history' in file:
                    df_temp = pd.read_csv(ffull, sep='\s*,\s*', engine='python')
                    data_by_files[ffull] = df_temp.groupby('"Time_Iter"').tail(1)  # we take the last time iteration
        full_history = pd.DataFrame()
        fs = sorted(data_by_files.keys())

        for i in range(len(fs)):
            # first, we check the CURRENT file, whether its value is greater than our restart_from; then we ignore it
            match = re.search("history_(\d{5}).csv", fs[i])
            if match and int(match.groups()[0]) - 1 > self.restart_from:
                continue  # the "if match" implies that this never happens for the first history file, which works as intended

            try:
                # if there are previous restart files, read the current file only up until where a more recent file starts
                # already has data (this can occur due to restarts)
                match = re.search("history_(\d{5}).csv", fs[i+1])
                # ^ the number in the NEXT file's name (fs[i+1]) is the number where THIS file (fs[i]) should stop
                if match:
                    maxlen = int(match.groups()[0])-1
                else:
                    maxlen = -1  # -1 would be the last, but most likely the last line we read is not the last INNER iter of the last time iter, so we skip one
            except IndexError:
                maxlen = -1

            df2 = data_by_files[fs[i]]
            if maxlen > 0:
                df2_trunc = df2[df2['"Time_Iter"'] <= maxlen]
            else:
                df2_trunc = df2.iloc[:maxlen]

            if full_history.isnull().values.all():
                full_history = df2_trunc
            elif not df2_trunc.isnull().values.all():
                full_history = pd.concat([full_history, df2_trunc])
            # else, we just keep full_history (i.e. do nothing)

        self.queue.put(full_history)
        return full_history

    def is_done(self):
        full_history = self.get_history()
        if dt.datetime.now().timestamp() - os.path.getmtime(self.logfile) > 10:  # check the file has not been modified in the last ten seconds
            with open(self.logfile) as fid:
                while True:  # check the file for exit messages
                    try:
                        line = next(fid)
                        if "Error Exit" in line:
                            return "Error Exit"
                        if "Exit Success" in line:  # TODO: find actual name
                            return "Exit Success"
                    except StopIteration:
                        break  # in this case we still need to check whether it has reached dynamic stability
        period = self._check_dynamically_stable(full_history, column_name=self.dyn_monitor_var)
        if period:
            val = f"Dynamically Stable. Period: {period}"
        else:
            val = "Running"
        return val

    def _check_dynamically_stable(self, df, column_name='"CD"', ):  # TODO: tune
        # Extract the specified column
        shift_max = self.shift_max
        l = self.dyn_stab_length
        max_trend_diff = self.max_trend_diff
        if len(df) < l+shift_max:
            return False
        column_values = df[column_name].values  # get raw values
        periods = []
        trend = pd.DataFrame({'data': column_values})['data'].ewm(halflife=shift_max).mean().values[-shift_max-l:-shift_max]
        for val in trend:
            if abs(trend[-1] - val)/l > max_trend_diff:
                return False  # if any value of the drift of the oscillation is outside the limits => not converged
        # all last l points are within max_trend_diff => we check whether there is an oscillatory behaviour
        # we do this by checking whether the signals "repetition period" (found by autocorrelation) ...
        # ... is INDEPENDENT of where we look at the signal, so we shift through shift_max
        for shift in range(1, shift_max):
            subvals = column_values[-l-shift:-shift]  # get last l values
            mn = np.mean(subvals)  # find mean, so we can offset by it
            shifted = subvals - mn  # the offset ensures that the values vary around 0, otherwise autocorrel. gives bad values
            c = np.correlate(shifted, shifted, 'same')[-l//2:]  # autocorrelate the data  # for some reason simple division does not work... but it makes sense anyway, just could cause the period to be slightly underestimated
            inflection = np.diff(np.sign(np.diff(c)))  # find the second-order differences
            peaks = (inflection < 0).nonzero()[0] + 1  # find where they are negative
            try:
                delay = peaks[c[peaks].argmax()]  # find the delay where the highest peak occurs (peak of subsequent periods will be lower due to autofill of zeros)
                periods.append(delay)
            except (ValueError, IndexError):
                return False
        if len(list(set(periods))) == 1:  # period no longer changes
            return periods[0]
        else:
            return False
