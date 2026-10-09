from tests.service_helpers import ServiceCase, document


class SharedService(ServiceCase):
    def test_worker_snapshot_and_persisted_metrics(self):
        doc=document();doc['sim_config']['shared_ride']={'enabled':True,'preference_weights':{'shared_only':1,'exclusive_only':1}}
        run=self.queue(doc)
        before=self.client.get(f'{self.api}/runs/{run}').json()['run_spec']
        self.assertEqual(before['sim_config']['shared_ride']['max_pickup_wait_s'],600)
        self.assertEqual(before['sim_config']['shared_ride']['fare_factor'],.7)
        doc['sim_config']['shared_ride']['max_pickup_wait_s']=900
        self.assertEqual(self.client.get(f'{self.api}/runs/{run}').json()['run_spec'],before)
        self.start(run);result=self.wait(run)
        self.assertEqual(result['status'],'succeeded',result.get('error'))
        response=self.client.get(f'{self.api}/runs/{run}/metrics')
        self.assertEqual(response.status_code,200,response.text)
        metrics=response.json()['summary']
        self.assertIn('shared.planned_pairs',metrics)
        self.assertEqual(metrics['shared.shared_only.gmv'],metrics['shared.shared_only.payout']+metrics['shared.shared_only.platform_fee'])
        self.assertEqual(result['run_spec'],before)
        self.assertEqual(self.client.get(f'{self.api}/health').json()['capabilities']['shared_ride_versions'],[1])

    def test_fallback_rejected_with_path(self):
        doc=document();doc['sim_config']['shared_ride']={'enabled':True,'preference_weights':{'shared_fallback_exclusive':1}}
        response=self.client.post(f'{self.api}/runs',json={'spec':doc})
        self.assertEqual(response.status_code,422)
        self.assertIn('sim_config.shared_ride.preference_weights',response.text)
