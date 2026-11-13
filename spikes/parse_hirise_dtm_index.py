"""Parse HiRISE PDS DTMCUMINDEX.TAB (fixed-width CSV) and list DTMs in a lat/lon box.
Usage: python parse_hirise_dtm_index.py DTMCUMINDEX.TAB latmin latmax lonmin_E lonmax_E [keyword]"""
import csv, sys
path, la0, la1, lo0, lo1 = sys.argv[1], *map(float, sys.argv[2:6])
kw = sys.argv[6].lower() if len(sys.argv) > 6 else None
seen = set()
with open(path, newline="", encoding="latin-1") as fh:
    for row in csv.reader(fh):
        row = [c.strip() for c in row]
        # columns per DTMCUMINDEX.LBL: 0 VOLUME_ID 1 FILE 2 HOST 3 INST 4 PRODUCT_ID 5 VER 6 TARGET 7 RATIONALE
        # 8 LEFT 9 RIGHT 10 SOURCE_DTM 11 DATA_TYPE 12 LINES 13 SAMPLES 14 NORTH_AZ 15 MINLAT 16 MAXLAT 17 MINLON 18 MAXLON 19 MAP_SCALE
        try:
            mnla, mxla, mnlo, mxlo = map(float, row[15:19])
        except ValueError:
            continue
        cla, clo = (mnla + mxla) / 2, (mnlo + mxlo) / 2
        if not (la0 <= cla <= la1 and lo0 <= clo <= lo1):
            continue
        if kw and kw not in row[7].lower():
            continue
        key = (row[4], row[1])
        if key in seen: continue
        seen.add(key)
        print(f"{row[4]} | {row[1]} | {cla:.3f}N {clo:.3f}E | scale {row[19]} m | {row[12]}x{row[13]} | {row[7]}")
