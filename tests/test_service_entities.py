"""S08-1/2: HTTP CRUD, active references and immutable run snapshots."""
import copy
from tests.service_helpers import ServiceCase, document


class TestEntities(ServiceCase):
    def test_crud_all_entities_and_snapshot(self):
        c, base = self.client, self.api
        vehicle = c.post(base + "/vehicle-types", json={"name": "car", "seats": 4})
        self.assertEqual(vehicle.status_code, 201)
        vid = vehicle.json()["id"]
        fleet = c.post(base + "/fleets", json={"name": "taxi", "composition": [{"vehicle_type": "car", "count": 20}]})
        self.assertEqual(fleet.status_code, 201)
        fid = fleet.json()["id"]
        station = c.post(base + "/charging-stations", json={"name": "hub", "node": 1})
        self.assertEqual(station.status_code, 201)
        sid = station.json()["id"]
        doc = document()
        doc["fleets"] = [{"ref": fid}]
        template = c.post(base + "/scenarios", json=doc)
        self.assertEqual(template.status_code, 201, template.text)
        tid = template.json()["id"]
        for resource, entity_id in (("vehicle-types", vid), ("fleets", fid), ("charging-stations", sid), ("scenarios", tid)):
            self.assertEqual(c.get(f"{base}/{resource}/{entity_id}").status_code, 200)
            self.assertEqual(len(c.get(f"{base}/{resource}").json()), 1)
        response = c.post(base + "/runs", json={"scenario_id": tid})
        self.assertEqual(response.status_code, 201, response.text)
        run_id = response.json()["id"]
        snapshot = response.json()["run_spec"]
        self.assertFalse("ref" in str(snapshot))
        self.assertEqual(snapshot["fleets"][0]["composition"][0]["count"], 20)
        self.assertEqual(c.delete(f"{base}/vehicle-types/{vid}").status_code, 409)
        self.assertEqual(c.put(f"{base}/vehicle-types/{vid}", json={"name": "new-car"}).status_code, 409)
        update = c.put(f"{base}/fleets/{fid}", json={"name": "renamed", "composition": [{"vehicle_type": "car", "count": 5}]})
        self.assertEqual(update.status_code, 200, update.text)
        self.assertEqual(update.json()["id"], fid)
        for resource, entity_id in (("scenarios", tid), ("fleets", fid), ("vehicle-types", vid), ("charging-stations", sid)):
            self.assertEqual(c.delete(f"{base}/{resource}/{entity_id}").status_code, 204)
            self.assertEqual(c.get(f"{base}/{resource}/{entity_id}").status_code, 404)
        self.assertEqual(c.get(f"{base}/runs/{run_id}").json()["run_spec"], snapshot)
        self.start(run_id)
        self.assertEqual(self.wait(run_id)["status"], "succeeded")
        self.assertEqual(c.post(base + "/vehicle-types", json={"name": "car"}).status_code, 201)

    def test_invalid_duplicate_deleted_and_unsupported(self):
        c, base = self.client, self.api
        bad = c.post(base + "/vehicle-types", json={"name": "car", "seats": True, "unknown": 2})
        self.assertEqual(bad.status_code, 422)
        self.assertTrue({"seats", "unknown"} <= {e["path"] for e in bad.json()["errors"]})
        self.assertEqual(c.post(base + "/fleets", json={"name": "f", "composition": [{"vehicle_type": "missing", "count": 2}]}).status_code, 422)
        vid = c.post(base + "/vehicle-types", json={"name": "car"}).json()["id"]
        self.assertEqual(c.post(base + "/vehicle-types", json={"name": "car"}).status_code, 409)
        other = c.post(base + "/vehicle-types", json={"name": "other"}).json()["id"]
        self.assertEqual(c.put(f"{base}/vehicle-types/{other}", json={"name": "car"}).status_code, 409)
        self.assertEqual(c.get(f"{base}/vehicle-types/{other}").json()["name"], "other")
        c.delete(f"{base}/vehicle-types/{vid}")
        doc = document()
        doc["vehicle_types"] = [{"ref": vid}]
        result = c.post(base + "/runs", json={"spec": doc})
        self.assertEqual(result.status_code, 422, result.text)
        self.assertEqual(c.get(base + "/runs").json(), [])
        for key, value in (("policy_group", {}), ("sim_config", {"pooling": {}})):
            doc = document()
            doc[key] = value
            self.assertEqual(c.post(base + "/runs", json={"spec": doc}).status_code, 422)
        self.assertEqual(c.post(base + "/runs", json={"scenario_id": True}).status_code, 422)
        self.assertEqual(c.get(base + "/policy-groups").status_code, 404)
        self.assertEqual(c.post(base + "/scenarios", json={"scenario": {"ref": 1}}).status_code, 422)

    def test_scenario_and_station_update_preserve_id(self):
        c, base = self.client, self.api
        for resource, doc, changed in (("charging-stations", {"name": "hub", "node": 1}, {"name": "hub2", "node": 2}),
                                       ("scenarios", document(), dict(document(), name="new-run"))):
            entity_id = c.post(base + "/" + resource, json=doc).json()["id"]
            response = c.put(f"{base}/{resource}/{entity_id}", json=changed)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["id"], entity_id)
            self.assertEqual(len(c.get(base + "/" + resource).json()), 1)
