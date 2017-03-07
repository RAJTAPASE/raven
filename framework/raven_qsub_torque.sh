#!/bin/bash

#eval `/apps/local/modules/bin/modulecmd bash load pbs python/2.7`

#cd $PBS_O_WORKDIR

#if [ `echo $MODULEPATH | grep -c '/apps/projects/moose/modulefiles'` -eq 0 ]; then   export MODULEPATH=$MODULEPATH:/apps/projects/moose/modulefiles; fi

#module load python/2.7
#eval `/apps/local/modules/bin/modulecmd bash load moose-dev-gcc python/3.2`

#export PYTHONPATH=$HOME/raven_libs/pylibs/lib/python2.7/site-packages

#module load pbs_is_loaded raven-devel-gcc

module load mpich

BASE_DIR=/cm/shared/apps/ncsu/projects/MOOSE/raven_libs
INSTALL_DIR="$BASE_DIR/install"
VE_DIR="$BASE_DIR/ve"
export PATH="$INSTALL_DIR/bin:$PATH"
source "$VE_DIR/bin/activate"

echo $PYTHONPATH

if test -n "$PBS_O_WORKDIR"; then
    cd $PBS_O_WORKDIR
fi

which python
which mpiexec
echo $COMMAND
$COMMAND
