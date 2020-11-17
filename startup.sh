#/bin/bash

if [ -f /app/appd.cfg ]; then
  pip install -U appdynamics || exit $?
  pyagent run -c /app/appd.cfg python -u -m mythic.main $@
else
  python -u -m mythic.main $@
fi
