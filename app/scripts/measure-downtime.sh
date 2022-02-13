#
# Measure the time it takes to recover from a failure in one/multiple of the elements.
#
# License: GPLv3
# Author: Raul Mahiques <rmahique@redhat.com>
#
# Usage:
#     Run it before the bringing down a node.
#

# NOTES: Room for improvements but it works

cmd="oc rsh -n openshift-storage `oc get pods -n openshift-storage | grep -i ceph-tools |head -1 | awk '{print $1}'`"


function check_health() {
if $cmd ceph -s |grep "health:[ ]*HEALTH_OK" &>/dev/null
then
  health=ok
else
    echo "$($cmd ceph -s |grep "health:") "
fi
mgr=$($cmd ceph mgr dump | grep -c '"available": true')
mon=`oc get pods -n openshift-storage -l app=rook-ceph-mon | grep -c Running`
mds=`oc get pods -n openshift-storage -l app=rook-ceph-mds | grep -c Running`
osd=`oc get pods -n openshift-storage -l app=rook-ceph-osd | grep -c Running`

echo "${mon}/5 MON, ${mgr}/1 MRG, ${mds}/2 MDS, ${osd}/3 OSD,  health: $health"
if (( $mon < 5 )) || (( $mgr < 1 )) || (( $mds < 2 )) || (( $osd < 3 )) || [[ "$health" != "ok" ]]
then
  echo "NOT OK"
  return 1
fi
}

failed=0
keep_going=1
s_time=0
while [[ $keep_going == 1 ]]
do
  check_health
        result=$?
  if [[ "$result" == "1" ]] && [[ $s_time == 0 ]]
  then
    s_time=`date +%s`
    echo "Failure ${s_time}"
  fi
  if [[ "$result" == "0" ]] && (( $s_time > 0 ))
  then
    e_time=`date +%s`
    keep_going=0
                echo "${e_time}"
    echo "It took $(( e_time - s_time ))s to recover"
    exit 0
  fi
done
