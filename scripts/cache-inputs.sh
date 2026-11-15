#!/usr/bin/env bash
set -euo pipefail
base="$1"
mkdir -p "$base/inputs"
fetch() {
    local url="$1" dest="$2"
    if ! test -s "$dest"; then
        curl -fsSL --retry 2 --max-time 180 "$url" -o "$dest.pending"
        test -s "$dest.pending"
        mv -- "$dest.pending" "$dest"
    fi
}
fetch 'https://raw.githubusercontent.com/bernardinelli/des_tno_catalog/8f254ca30fa0e8fc1576a5a9fad7300124d3b3ee/y6_des_tnos_color.fits' \
    "$base/inputs/des-y6-tno.fits"
fetch 'https://ssd.jpl.nasa.gov/ftp/eph/planets/bsp/de440s.bsp' "$base/inputs/de440s.bsp"
sha256sum "$base/inputs/des-y6-tno.fits" "$base/inputs/de440s.bsp"
