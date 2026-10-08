"""Cut the Hồ Gươm test fixture out of the Vietnam PBF (dev tool, run once; the output is committed).

    python tests/data/osm/make_fixture.py data/osm/cache/vietnam-261006.osm.pbf

Keeps the kept-class highway ways, buildings and POIs touching a ~1.6 km² box around Hồ Gươm, plus the ward
relations (admin_level 6) overlapping it with their complete member ways. One way gets ``motorcycle=no`` added
(simulated motorbike ban, for the vehicle-group tests) — the only change to the OSM data.
"""
import sys
from pathlib import Path

import osmium

from kami.osm import load_config
from kami.osm.extract import extract
from kami.osm.geo import Polygon

HERE = Path(__file__).resolve().parent
BOX = (105.8445, 21.0225, 105.8585, 21.0345)        # lon0, lat0, lon1, lat1
FAKE_BAN_WAY_NAME = "Phố Đinh Tiên Hoàng"


def main(pbf: str) -> None:
    cfg = load_config("hanoi")
    keep = set(cfg["highway"])
    x0, y0, x1, y1 = BOX
    box_poly = Polygon([[[(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]]])
    data = extract(pbf, box_poly, cfg["highway"], "6", margin_deg=0.0)
    rel_ids = {b.id for b in data.boundaries}
    node_ids, way_ids, member_ways = set(), set(), set()
    ban_way = None
    for o in osmium.FileProcessor(pbf).with_locations().with_filter(
            osmium.filter.KeyFilter("highway", "building", "amenity", "shop", "office")):
        if o.is_way():
            pts = [(n.ref, n.lon, n.lat) for n in o.nodes]
            hw = o.tags.get("highway")
            if hw is not None and hw not in keep:
                continue
            if any(x0 <= lon <= x1 and y0 <= lat <= y1 for _, lon, lat in pts):
                way_ids.add(o.id)
                node_ids.update(r for r, _, _ in pts)
                if hw and ban_way is None and o.tags.get("name") == FAKE_BAN_WAY_NAME:
                    ban_way = o.id
        elif o.is_node() and x0 <= o.lon <= x1 and y0 <= o.lat <= y1:
            node_ids.add(o.id)
    for o in osmium.FileProcessor(pbf).with_filter(osmium.filter.EntityFilter(osmium.osm.RELATION)).with_filter(
            osmium.filter.IdFilter(rel_ids)):
        member_ways.update(m.ref for m in o.members if m.type == "w")
    for o in osmium.FileProcessor(pbf).with_filter(osmium.filter.EntityFilter(osmium.osm.WAY)).with_filter(
            osmium.filter.IdFilter(member_ways)):
        node_ids.update(n.ref for n in o.nodes)
    way_ids |= member_ways
    out = HERE / "hoan_kiem.osm.pbf"
    out.unlink(missing_ok=True)
    writer = osmium.SimpleWriter(str(out))
    n = {"node": 0, "way": 0, "relation": 0}
    for o in osmium.FileProcessor(pbf).with_filter(osmium.filter.IdFilter(node_ids | way_ids | rel_ids)):
        if o.is_node() and o.id in node_ids:
            writer.add_node(o.replace(user="", uid=0, changeset=0))
            n["node"] += 1
        elif o.is_way() and o.id in way_ids:
            if o.id == ban_way:
                tags = dict((t.k, t.v) for t in o.tags)
                tags["motorcycle"] = "no"
                writer.add_way(o.replace(tags=tags, user="", uid=0, changeset=0))
            else:
                writer.add_way(o.replace(user="", uid=0, changeset=0))
            n["way"] += 1
        elif o.is_relation() and o.id in rel_ids:
            writer.add_relation(o.replace(user="", uid=0, changeset=0))
            n["relation"] += 1
    writer.close()
    print(out, out.stat().st_size, n, "fake ban on way", ban_way)


if __name__ == "__main__":
    main(sys.argv[1])
