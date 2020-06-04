import subprocess
import re
from queue import Queue
from threading import Thread
from time import time

LTSpicePath = 'C:\Program Files\LTC\LTspiceXVII\XVIIx64.exe'
file = 'example LTSpice sims/BuckBoost'

returned_value = subprocess.run([LTSpicePath, '-netlist', file+'.asc'], shell=True, check=True)

print('returned value:', returned_value)

jobslist=[]

lines = []

class LTSpiceWorker(Thread):

    def __init__(self, queue):
        Thread.__init__(self)
        self.queue = queue

    def run(self):
        while True:
            # Get the work from the queue and expand the tuple
            LTSpicePath_, job = self.queue.get()
            try:
                returned_value = subprocess.run([LTSpicePath_, '-b', job], shell=True, check=True)
                print('job:{} returned:{}'.format(job,returned_value))
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

    paramStrList = []
    for value in values:
        paramStrList.append('.param {} {}'.format(var, value))
##        print('.param {} {}'.format(var, value))
    return paramStrList


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
                    line = parseStepDirec(line)
                lines.append(line)
                print("Line {:>4}:  {:<8}  {}".format(cnt, direc['str'], line))
                    
        if not isaspecialdirec:
            lines.append(line.strip())
            print("Line {:>4}:  {:<8}  {}".format(cnt, '', line.strip()))

        line = fp.readline()
        cnt += 1

    print()
    output = []
    output.append([])
    evalLines(output, output[0], 0, len(lines))
    for i in range(0, len(output)):
        out = open('j{}.net'.format(i),'w')
        for line in output[i]:
            out.write('{}\r\n'.format(line))
        jobslist.append(str(out.name))
        out.close()
 
start = time()
##for job in jobslist:
##    returned_value = subprocess.run([LTSpicePath, '-b', job], shell=True, check=True)
##    print('job:{} returned:{}'.format(job,returned_value))
##    end = time()
##    elapsed = end - start
##    print('elapsed: ', elapsed)

queue = Queue()
for x in range(32):
    worker = LTSpiceWorker(queue)
    worker.daemon = True
    worker.start()

for job in jobslist:
    queue.put((LTSpicePath, job))
queue.join()
end = time()
elapsed = end - start
print('elapsed: ', elapsed)
    
