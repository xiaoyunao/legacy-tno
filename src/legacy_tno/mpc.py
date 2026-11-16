"""Export anonymous W84 astrometry in the MPC 80-column observation format."""
from astropy import units as u
from astropy.coordinates import Angle
from astropy.time import Time


def export_mpc(track, packed):
    dates = Time(track["mjd_tdb"], format="mjd", scale="tdb").utc
    rows = []
    for t, ra, dec in zip(dates, track["ra_deg"], track["dec_deg"], strict=True):
        year, month, day, *_ = t.ymdhms
        midnight = Time(f"{year:04d}-{month:02d}-{day:02d}", scale="utc")
        date = f"{year:04d} {month:02d} {day+(t-midnight).to_value(u.day):09.6f}"
        a = Angle(ra*u.deg).to_string(u.hourangle, sep=" ", precision=3, pad=True)
        d = Angle(dec*u.deg).to_string(u.deg, sep=" ", precision=2, pad=True, alwayssign=True)
        row = f"     {packed}  C{date}{a}{d}{'':21}W84"
        if len(row) != 80:
            raise ValueError("Find_Orb input overflowed MPC observation columns")
        rows.append(row)
    return "\n".join(rows) + "\n"
