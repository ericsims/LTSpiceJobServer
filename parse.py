import subprocess
import re
from queue import Queue
from threading import Thread
from time import time
import itertools
import math
import string
import random

LTSpicePath = 'C:\Program Files\LTC\LTspiceXVII\XVIIx64.exe'
file = 'example LTSpice sims/BuckBoost'
##file = 'example LTSpice sims/MonteCarlo'

returned_value = subprocess.run([LTSpicePath, '-netlist', file+'.asc'], shell=True, check=True)

print('returned value:', returned_value)

lines = []

stepvals = []
stepvars = []

class LTSpiceWorker(Thread):

    def __init__(self, queue):
        Thread.__init__(self)
        self.queue = queue

    def run(self):
        while True:
            # Get the work from the queue and expand the tuple
            LTSpicePath_, job = self.queue.get()
            try:
                returned_value = subprocess.run([LTSpicePath_, '-b', '{}.net'.format(job)], shell=True, check=True)
##                print('job:{} returned:{}'.format(job,returned_value))
            finally:
                self.queue.task_done()

def parseStepDirec(stepdirective):
##    print("step: ", stepdirective)
    str_split = stepdirective.split()
    mode = None
    var = None
    if str_split[1] == 'param':
        var = str_split[2]
        if str_split[3] == 'list':
            mode = 'list'
            params = str_split[4:]
        else:
            mode = 'lin'
            params = str_split[3:]
    elif str_split[1] == 'oct':
        mode = 'oct'
        var = str_split[3]
        params = str_split[4:]
    elif str_split[1] == 'dec':
        mode = 'dec'
        var = str_split[3]
        params = str_split[4:]

    if mode == 'list':
        values = params
    elif mode == 'lin':
        values = []
        if not('.' in params[0] or '.' in params[1] or '.' in params[2]):
            start = int(params[0])
            end = int(params[1])
            inc = int(params[2])
        else:
            start = float(params[0])
            end = float(params[1])
            inc = float(params[2]) 
        x=start
        while x < end:
          values.append(x)
          x += inc
        values.append(end)
    # TODO parse dec
    # TODO parse oct
    else:
        raise NameError('not a valid step command???')

##    print("mode: {}, var: {}, params:{}".format(mode,var,params))
##    print("values:{}".format(values))
    stepvars.append(var)
    stepvals.append(tuple(values[:]))
    return ''

##    paramStrList = []
##    for value in values:
##        paramStrList.append('.param {} {}'.format(var, value))
##        print('.param {} {}'.format(var, value))
##    return paramStrList


specialdirectives=[\
    {'str':'.lib', 'keepcase':True, 'function':None},\
    {'str':'.wave', 'keepcase':True, 'function':None},\
    {'str':'.step', 'keepcase':False, 'function':parseStepDirec}]

    
def evalLines(parent, bucket, start, end):
    for i in range(start,end):
        if isinstance(lines[i], list):
            a = lines[i][:]
            a0 = a.pop(0)
            while a:
                newbuck = bucket[:]
                newbuck.append(a.pop(0))
                evalLines(parent, newbuck, i+1, end)
                parent.append(newbuck)
            bucket.append(a0)
        else:
            bucket.append(lines[i])

with open(file+".net", 'r') as fp:
    line = fp.readline()
    cnt = 0 
    while line:
        # replace any double spaces
        line = re.sub(re.compile(' +'), ' ', line)

        isaspecialdirec = False
        for direc in specialdirectives:
            line_templower = line.lower().strip()
            if line_templower.startswith(direc['str']):
                isaspecialdirec = True
                if not direc['keepcase']:
                    line=line_templower
                else:
                    line=line.strip()
                if not direc['function'] is None:
                    line = direc['function'](line)
                lines.append(line.strip())
                print("Line {:>4}:  {:<8}  {}".format(cnt, direc['str'], line))
                    
        if not isaspecialdirec:
            lines.append(line.strip())
            print("Line {:>4}:  {:<8}  {}".format(cnt, '', line.strip()))

        line = fp.readline()
        cnt += 1

    print()
    
def execRuns(workerCount_):
    runList_ = []
    combinations = [list(sub) for sub in list(itertools.product(*stepvals))[:]]
    numberofsteps = len(combinations)
    indexlist = []
    if numberofsteps > 1:
        lookuptable = []
        j = 0
        s = 0
        for vi in range(numberofsteps):
            indexlist.append((j,s))
            print('j{}, s{}, vi{}, v{}'.format(j,s,vi,combinations[vi]))
            if not (len(lookuptable) > j):
                lookuptable.append([])
            lookuptable[j].append(combinations[vi])
            j += 1
            if j >= workerCount_:
                j = 0
                s += 1
        for j in range(len(lookuptable)):
            out = open('j{}.net'.format(j),'w')
            runList_.append('j{}'.format(j))
            newlines = lines[:]
##            print()
##            print('j{}'.format(j))
            dummylength = len(lookuptable[j])
            if dummylength > 1:
        ##        dummyvar = ''.join(random.choice(string.ascii_lowercase) for i in range(16))
                dummyvar = 'temporarystepvarx'
##                print('.step param {} 0 {} 1'.format(dummyvar,dummylength-1))
                newlines.insert(len(newlines)-2,'.step param {} 0 {} 1'.format(dummyvar,dummylength-1))
                for x in range(len(stepvars)):
                    cmd = '.param {} table({}'.format(stepvars[x],dummyvar)
                    for y in range(len(lookuptable[j])):
                        cmd+=(',{},{}'.format(y,lookuptable[j][y][x]))
                    cmd+=(')')
                    newlines.insert(len(newlines)-2,cmd)
##                    print(cmd)
            else:
                for x in range(len(stepvars)):
                    cmd = '.param {} {}'.format(stepvars[x],lookuptable[j][0][x])
                    newlines.insert(len(newlines)-2,cmd)
##                    print(cmd)
            for line in newlines:
                out.write('{}\n'.format(line))
            out.close()
    else:
        indexlist.append((0,0))
        out = open('j0.net','w')
        runList_.append('j0')
        for line in lines:
           out.write('{}\n'.format(line))
        out.close()


    
    print()
    print('doing {} steps in {} runs with {} workers'.format(len(combinations), len(runList_), workerCount_))
    start = time()
    queue = Queue()
    for x in range(workerCount_):
        worker = LTSpiceWorker(queue)
        worker.daemon = True
        worker.start()

    for run in runList_:
        queue.put((LTSpicePath, run))
    queue.join()
    end = time()
    elapsed = end - start
    print('elapsed: ', elapsed)
    return (runList_,indexlist)

(runs, indexlist) = execRuns(16)

import ltspice
import struct

outdata = [None] * len(runs)
for r in range(len(runs)):
    outdata[r] = ltspice.Ltspice('{}.raw'.format(runs[r]))
    outdata[r].parse()

totalpoints = 0
for dat in outdata:
    totalpoints += dat._point_num

##totalpoints = outdata[0]._point_num
# TODO: this only works for TRANS...
out = open('outdata.raw','w', encoding='UTF16', newline='')
out.write('Title: * {}\n'.format('i forgot what the input file was'))
out.write('Date: {}\n'.format(outdata[0].date.strip()))
out.write('Plotname: {}\n'.format(outdata[0].plot_name.strip())) # TODO: copying this name might not always work
out.write('Flags: {}\n'.format(outdata[0].flags.strip())) # TODO: copying this name might not always work
out.write('No. Variables: {}\n'.format(outdata[0]._variable_num))
out.write('No. Points: {}\n'.format(totalpoints))
out.write('Offset: {}\n'.format('0.0000000000000000e+000')) # not sure how to deal with this yet
out.write('Command: {}\n'.format('idk does this even matter')) # does this matter?
out.write('Variables:\n')
for i in range(outdata[0].getVariableNumber()):
    out.write('\t{}\t{}\t{}\n'.format(i, outdata[0].getVariableNames()[i], outdata[0].getVariableTypes()[i]))
out.write('Binary:\n') # again, this might now always work
out.close()
out = open('outdata.raw','ab')
##indexlist=[(14,0),(15,0)]
for (j,s) in indexlist:
    print('j:{} s{} {} - {}'.format(j,s,outdata[j]._case_split_point[s],outdata[j]._case_split_point[s+1]))
    for l in range(outdata[j]._case_split_point[s],outdata[j]._case_split_point[s+1]):
        out.write(struct.pack('d',outdata[j].time_raw[l]))
        out.write(outdata[j].data_raw[l][2:].tobytes())
##        print('{} {} {}'.format(l,struct.pack('d',outdata[0].time_raw[l]),outdata[0].data_raw[l][2:].tobytes()))
    out.flush()
out.close()

##if steps > 1:
    # stepped sim
    

    
