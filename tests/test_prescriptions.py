"""Session targets from history."""
from datetime import date, datetime, timedelta

from training_agent.core.models import Activity, Intensity, Sport
from training_agent.planner.prescriptions import classify, prescribe

TODAY = date(2026, 11, 4)


def act(sport, minutes, km, hr=None, pe=None, days_ago=10, i=[0]):
    i[0] += 1
    return Activity(id=f"t:{i[0]}", source="garmin", sport=sport,
                    start_time=datetime.combine(TODAY - timedelta(days=days_ago), datetime.min.time()),
                    duration_s=minutes * 60, distance_m=km * 1000 if km else None, avg_hr=hr, perceived_exertion=pe)


def runs():
    easy = [act(Sport.RUN, 40, 5.9, hr=135), act(Sport.RUN, 45, 6.5, hr=138), act(Sport.RUN, 50, 7.3, hr=140)]  # about 6.8 min/km
    hard = [act(Sport.RUN, 60, 10.0, hr=172), act(Sport.RUN, 65, 11.0, hr=170), act(Sport.RUN, 55, 9.3, hr=175)]  # about 5.9 min/km
    return easy + hard


def test_runs_go_by_heart_rate_rides_go_by_duration():
    assert classify(act(Sport.RUN, 40, 5, hr=130), 195) == Intensity.EASY
    assert classify(act(Sport.RUN, 40, 5, hr=155), 195) == Intensity.MODERATE
    assert classify(act(Sport.RUN, 40, 5, hr=175), 195) == Intensity.HARD
    assert classify(act(Sport.RUN, 40, 5, pe=3), 195) == Intensity.EASY  # no heart rate: the athlete's rating
    assert classify(act(Sport.RUN, 40, 5), 195) is None
    assert classify(act(Sport.BIKE, 90, 30, hr=175), 195) == Intensity.EASY  # under 2 h, whatever the heart rate
    assert classify(act(Sport.BIKE, 155, 55, hr=140), 195) == Intensity.MODERATE  # 2-5 h
    assert classify(act(Sport.BIKE, 360, 120), 195) == Intensity.HARD  # over 5 h
    assert classify(act(Sport.BIKE, 200, 60), 195, ride_bands=(150, 240)) == Intensity.MODERATE  # bands are configurable


def test_easy_run_uses_the_athletes_easy_pace_and_heart_rate():
    p = prescribe(Sport.RUN, Intensity.EASY, runs(), today=TODAY)
    assert 6.7 <= p.pace_min_per_km <= 6.9 and p.based_on == 3
    assert 133 <= p.hr_low <= p.hr_high <= 141  # widened to at least 6 bpm
    assert "3 of your easy run" in p.note


def test_fixed_distance_kind_sets_distance_and_time():
    p = prescribe(Sport.RUN, Intensity.EASY, runs(), kind="10k", today=TODAY)
    assert p.distance_km == 10.0 and round(p.duration_min) == round(10 * p.pace_min_per_km)


def test_hard_run_is_faster_than_easy():
    easy, hard = (prescribe(Sport.RUN, i, runs(), today=TODAY) for i in (Intensity.EASY, Intensity.HARD))
    assert hard.pace_min_per_km < easy.pace_min_per_km


def test_long_ride_is_longer_than_short_ride():
    rides = [act(Sport.BIKE, m, m / 3, hr=140) for m in (130, 170, 210, 250, 290)]  # all moderate (2-5 h)
    short = prescribe(Sport.BIKE, Intensity.MODERATE, rides, kind="short", today=TODAY)
    long_ = prescribe(Sport.BIKE, Intensity.MODERATE, rides, kind="long", today=TODAY)
    assert long_.duration_min > short.duration_min and long_.distance_km > short.distance_km
    assert round(short.speed_kmh) == 20


def test_rides_without_heart_rate_still_count():
    rides = [act(Sport.BIKE, 90, 30) for _ in range(3)]  # no heart rate at all
    p = prescribe(Sport.BIKE, Intensity.EASY, rides, today=TODAY)
    assert p.based_on == 3 and p.speed_kmh == 20.0


def test_falls_back_to_defaults_with_too_little_history():
    p = prescribe(Sport.BIKE, Intensity.HARD, [act(Sport.BIKE, 400, 130, hr=140)], today=TODAY)
    assert p.based_on == 1 and "Default targets" in p.note and p.duration_min == 330


def test_volume_factor_shortens_the_session_but_not_the_pace():
    full = prescribe(Sport.RUN, Intensity.EASY, runs(), today=TODAY)
    tired = prescribe(Sport.RUN, Intensity.EASY, runs(), today=TODAY, volume_factor=0.75)
    assert tired.duration_min < full.duration_min and tired.pace_min_per_km == full.pace_min_per_km


def test_old_sessions_are_ignored():
    old = [act(Sport.RUN, 40, 5.9, hr=135, days_ago=400) for _ in range(5)]
    assert prescribe(Sport.RUN, Intensity.EASY, old, today=TODAY).based_on == 0


def test_rest_and_unsupported_sports_have_no_targets():
    assert prescribe(Sport.RUN, Intensity.REST, runs(), today=TODAY) is None
    assert prescribe(Sport.OTHER, Intensity.EASY, runs(), today=TODAY) is None


def test_gym_uses_all_sessions_and_notes_the_effort():
    gym = [act(Sport.GYM, m, None, hr=95) for m in (45, 50, 55)]
    p = prescribe(Sport.GYM, Intensity.MODERATE, gym, today=TODAY)
    assert p.duration_min == 50 and p.distance_km is None and "weights" in p.note


def test_harder_runs_are_shorter_than_easy_ones():
    runs_ = ([act(Sport.RUN, 60, 8.8, hr=135) for _ in range(3)]
             + [act(Sport.RUN, 70, 11.0, hr=155) for _ in range(3)]   # moderate runs were longer
             + [act(Sport.RUN, 80, 14.0, hr=175) for _ in range(3)])  # and so were hard ones
    easy, mod, hard = (prescribe(Sport.RUN, i, runs_, today=TODAY) for i in (Intensity.EASY, Intensity.MODERATE, Intensity.HARD))
    assert mod.duration_min == round(0.8 * easy.duration_min) and hard.duration_min == round(0.6 * easy.duration_min)
    assert hard.pace_min_per_km < easy.pace_min_per_km


def test_harder_rides_are_longer_and_report_typical_climbing():
    rides = ([act(Sport.BIKE, 90, 30, hr=140) for _ in range(3)] + [act(Sport.BIKE, 380, 120, hr=140) for _ in range(3)])
    for r in rides:
        r.elevation_gain_m = 550.0 if r.duration_s < 7200 else 2200.0
    easy, hard = prescribe(Sport.BIKE, Intensity.EASY, rides, today=TODAY), prescribe(Sport.BIKE, Intensity.HARD, rides, today=TODAY)
    assert hard.duration_min > easy.duration_min and easy.elevation_gain_m == 550 and hard.elevation_gain_m == 2200
    assert "under 120 min count as easy" in easy.note


def test_heart_rate_range_is_never_needlessly_narrow():
    rides = [act(Sport.BIKE, 120, 40, hr=147) for _ in range(3)]
    p = prescribe(Sport.BIKE, Intensity.MODERATE, rides, today=TODAY)
    assert p.hr_high - p.hr_low >= 6
