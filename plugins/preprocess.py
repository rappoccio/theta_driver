#
# Preprocess plugin to prepare for a grid submission
# Victor E. Bazterra UIC (2012)
#


def parse_model(model):
    """ Parse model command line """
    info = model.split(':')
    assert len(info) > 1, 'Syntax error when parsing model command line.'
    module = info[0]
    assert module != '', 'Syntax error no model name.'
    opts = info[1].split(',')
    args = {}
    for opt in opts:
        key = opt.split('=')[0]
        value = opt.split('=')[1]
        args[key.lstrip().rstrip()] = value.lstrip().rstrip()
    return module, args


from optparse import OptionParser

usage = 'usage: %prog postprocess [options] [file1] [file2] ...\n'
usage = usage + 'Prepare theta for grid submission.'

parser = OptionParser(
    usage = usage
)

parser.add_option(
    '--model', type='string',
    help='Input model and argments in the format "file: arg1 = val1, arg2 = val2, ..."'
)
parser.add_option(
    '--analysis', type='string', default='summary',
    help='Analysis to be done to the model [default: %default]."'
)
parser.add_option(
    '--workdir', type='string',
    help='Working directory of the driver."'
)
parser.add_option(
    '--remotedir', type='string',
    help='Remote directory to put all the produced theta files."'
)

(options, args) = parser.parse_args()

import os

if 'THETA_PATH' not in os.environ:
    raise EnvironmentError('Missing THETA_PATH environment variable, source setup first.')

import exceptions

if not options.workdir:
    raise exceptions.ValueError('Undefined working directory.') 

# Create working directory
if not os.path.exists(options.workdir):
    os.makedirs(options.workdir)

# Processing model information
module, opts = parse_model(options.model) 

import shutil

# Copy the content of the model in 
shutil.copy(module+'.py', '%s/analysis.py' % options.workdir)

# Append the model file by adding the options and actions
file = open('%s/analysis.py' % options.workdir, 'a')
file.write('\n\n')
file.write('# Code introduced by theta_driver\n\n')
file.write('# Building the statistical model\n')
file.write('args = %s\n\n' % str(opts))
file.write('model = build_model(**args)\n\n')
if options.analysis == 'summary':
    file.write('model_summary(model)\n')
elif options.analysis == 'bayesian':
    file.write('results = bayesian_limits(model, run_theta = False)\n')
elif options.analysis == 'cls-lr':
    file.write("results = cls_limits(model, ts = 'lr', run_theta = False, write_debuglog = False)\n")
elif options.analysis == 'cls-lhclike':
    file.write("results = cls_limits(model, ts = 'lhclike', run_theta = False, write_debuglog = True)\n")
file.close()

commands = []

# Link all the file dependency
files = []
for arg in args:
    if not os.path.isfile(arg): continue
    commands.append('ln -sf ../%s %s' % (arg, options.workdir))
    files.append(os.path.basename(arg))

# Execute theta to produce only cfg files
if os.path.exists('%s/analysis' % options.workdir):
    commands.append('cd %s; rm -rf analysis' % options.workdir)
commands.append('cd %s; %s/utils/theta-auto.py analysis.py' % (options.workdir, os.environ['THETA_PATH']))

if not options.analysis == 'summary':
    commands = commands + [
        'cd %s; tar cz analysis/ > analysis.tgz' % options.workdir,
        'cp %s/utils/grid_theta_executable.* %s' % (os.environ['THETA_DRIVER_PATH'], options.workdir)
    ]

    if not os.path.isfile('%s/gridpack/gridpack.tgz' % os.environ['THETA_PATH']):
        commands.append('cd %s; ./build.sh' % os.environ['THETA_PATH'])
    commands.append('cp %s/gridpack/gridpack.tgz %s' % (os.environ['THETA_PATH'], options.workdir))

import subprocess
for command in commands:
    print command
    subprocess.call( [command], shell=True )

# Prepare crab cfg file

# This is only if a report is not issued
if options.analysis == 'summary':
    sys.exit(0)

# Reads how many cfg files are generated
njobs = 0
dir = os.listdir('%s/analysis' % options.workdir)
for file in dir:
    if '.cfg' in file: 
        njobs = njobs + 1

import string
file = open('%s/utils/grid_theta_crab.cfg' % os.environ['THETA_DRIVER_PATH'])
cfg = string.Template(file.read())
file.close()
cfg = cfg.safe_substitute(
    njobs = njobs, 
    user = os.environ['USER'],
    files = ','.join(files),
    remotedir = options.remotedir 
)
file = open('%s/grid_theta_crab.cfg' % options.workdir, 'w')
file.write(cfg)
