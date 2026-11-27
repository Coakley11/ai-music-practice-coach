"""Authorized isolated hosted recheck; retains every existing fixture."""
import argparse
import importlib.util
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('phase6',ROOT/'scripts/verify_music_phase6_hosted.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--approved-project',required=True,choices=[m.PROJECT])
    parser.add_argument('--preflight-and-installation-verified',action='store_true')
    args=parser.parse_args()
    if not args.preflight_and_installation_verified:
        parser.error('Confirm existing installation/preflight before synthetic writes')
    anon,service=m.load_credentials(args.config)
    client=m.Client(anon,service)
    m.verify_access(client)
    response=client.call('GET','/auth/v1/admin/users?page=1&per_page=100',backend=True)
    m.check(response.status_code==200,'Existing synthetic account inventory')
    data=response.json()
    m.check(not data.get('next_page'),'Account inventory complete')
    users=[u['id'] for u in data.get('users',[]) if (u.get('user_metadata') or {}).get('music_phase6_synthetic')]
    def snapshot():
        rows=[]
        for uid in sorted(users):
            for table in ('customers','entitlements'):
                r=client.call('GET',f'/rest/v1/music_billing_{table}?app_user_id=eq.{uid}&select=*',backend=True)
                m.check(r.status_code==200,'Retained fixture read')
                rows.append((uid,table,r.json()))
        return rows
    before=snapshot()
    print('PASS: existing synthetic accounts inventoried; retained customer/entitlement snapshot held in memory',flush=True)
    m.run(client)
    m.check(snapshot()==before,'Retained customer/entitlement records unchanged')
    for uid in users:
        r=client.call('GET','/auth/v1/admin/users/'+uid,backend=True)
        m.check(r.status_code==200 and r.json().get('id')==uid,'Retained synthetic Auth account still exists')
    print('PASS: all pre-existing synthetic Auth accounts retained; existing customer/entitlement records unchanged',flush=True)
if __name__=='__main__':
    try: main()
    except Exception as error:
        if isinstance(error,(ValueError,RuntimeError)): print(str(error),file=sys.stderr)
        else: print('Hosted recheck failed; details suppressed',file=sys.stderr)
        sys.exit(1)
