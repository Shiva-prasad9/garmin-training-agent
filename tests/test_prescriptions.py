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


def test_classification_by_heart_rate_and_by_rating():
    assert classify(act(Sport.RUN, 40, 5, hr=130), 195) == Intensity.EASY
    assert classify(act(Sport.RUN, 40, 5, hr=155), 195) == Intensity.MODERATE
    assert classify(act(Sport.RUN, 40, 5, hr=175), 195) == Intensity.HARD
    assert classify(act(Sport.BIKE, 120, 40, pe=3), 195) == Intensity.EASY  # no heart rate: the athlete's rating
    assert classify(act(Sport.BIKE, 120, 40, pe=8), 195) == Intensity.HARD
    assert classify(act(Sport.BIKE, 120, 40), 195) is None


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
    rides = [act(Sport.BIKE, m, m / 3, hr=140) for m in (60, 90, 120, 180, 240)]  # all easy
    short = prescribe(Sport.BIKE, Intensity.EASY, rides, kind="short", today=TODAY)
    long_ = prescribe(Sport.BIKE, Intensity.EASY, rides, kind="long", today=TODAY)
    assert long_.duration_min > short.duration_min and long_.distance_km > short.distance_km
    assert round(short.speed_kmh) == 20


def test_rides_without_heart_rate_count_through_the_rating():
    rides = [act(Sport.BIKE, 120, 40, pe=3) for _ in range(3)]
    p = prescribe(Sport.BIKE, Intensity.EASY, rides, today=TODAY)
    assert p.based_on == 3 and p.speed_kmh == 20.0


def test_falls_back_to_defaults_with_too_little_history():
    p = prescribe(Sport.BIKE, Intensity.HARD, [act(Sport.BIKE, 60, 25, hr=175)], today=TODAY)
    assert p.based_on == 1 and "Default targets" in p.note and p.speed_kmh == 27.0


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


def test_harder_sessions_are_shorter_than_easy_ones():
    rides = ([act(Sport.BIKE, 240, 80, hr=140) for _ in range(3)]
             + [act(Sport.BIKE, 300, 120, hr=160) for _ in range(3)]    # moderate rides were long
             + [act(Sport.BIKE, 330, 140, hr=175) for _ in range(3)])   # and so were hard ones
    easy, mod, hard = (prescribe(Sport.BIKE, i, rides, today=TODAY)
                       for i in (Intensity.EASY, Intensity.MODERATE, Intensity.HARD))
    assert mod.duration_min == round(0.8 * easy.duration_min) and hard.duration_min == round(0.6 * easy.duration_min)
    assert hard.distance_km < easy.distance_km and hard.speed_kmh > easy.speed_kmh


def test_heart_rate_range_is_never_needlessly_narrow():
    rides = [act(Sport.BIKE, 120, 40, hr=147) for _ in range(3)]
    p = prescribe(Sport.BIKE, Intensity.MODERATE, rides, today=TODAY)
    assert p.hr_high - p.hr_low >= 6
