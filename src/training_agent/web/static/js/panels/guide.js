// User guide: plain-language help, collapsed by default. Open it from the "Guide" link in the header.
import { el } from "../util.js";

const SECTIONS = [
  ["What this page is", [
    "A personal training dashboard. It reads your Garmin data, learns what is normal for you, and suggests how hard to train today.",
    "Everything runs and stays on this computer. The suggestion is advice: you always decide.",
  ]],
  ["Status window", [
    "Shows last night's HRV, sleep score, sleep length and resting heart rate against your own usual values (the median of your last 4 weeks).",
    "The bar shows where today sits: the shaded band is your normal range. Far outside it is flagged as notable or unusual.",
    "The 7-day line says whether the weekly direction is improving, steady or declining.",
  ]],
  ["Insights page", [
    "Open Insights in the left menu. The gold card at the top is the single most useful thing to do right now, with the reason. It is chosen from your own data: sleep, recovery signals, training load, how easy your easy days really are, how regular you are, and how your long sessions are progressing.",
    "The Insights cards below it show every finding. Each is marked Needs action, Keep an eye on it, or On track, says why it matters, and tells you what to do. Open The numbers to see the figures behind it.",
    "These are suggestions from patterns in your data, not medical advice. Thresholds are first guesses and will be tuned after you have used the dashboard for a while.",
  ]],
  ["Daily quest (today's plan)", [
    "Allowed up to: the highest intensity your recovery signals and recent training allow. Rules can only lower this, never raise it.",
    "Recommended: the session the planner suggests, with distance, pace or speed, and a heart-rate range taken from your own past sessions.",
    "Options: rest, easy, moderate and hard. You can pick any of them. Choosing above what is allowed shows a warning and changes tomorrow's advice, but it is never blocked.",
    "Plan this: saves your choice. Undo removes it. Coach note (if present): a short explanation from the language model, which can only choose within what the rules allow.",
  ]],
  ["This week", [
    "The weekly template: 1 run, 2 rides (short and long), 3 gym sessions, 1 rest day. Done sessions are ticked from your recorded workouts.",
    "If the week is behind, the planner drops a session (gym first) instead of piling everything on the last days.",
  ]],
  ["Trends", [
    "HRV, sleep, resting heart rate and Body Battery over the chosen range (7, 10 or 14 days). Use the buttons at the top to change it.",
    "Short nights and obviously partial readings are ignored so they do not distort your baseline.",
  ]],
  ["Activities", [
    "Your recent workouts with duration, distance, average heart rate and time in heart-rate zones (Z1 easy to Z5 maximal).",
    "Load is Garmin's own training load for the workout. The chart sums it by week and sport.",
    "Click a ride, run or hike to open its details: moving and elapsed time, speed or pace, climbing, heart rate and zones, charts of heart rate, speed and elevation along the distance, and the route. Move over a chart to see the matching point on the route.",
    "Details are downloaded with the daily run. For older workouts run: .venv/bin/python scripts/backfill.py --days 180 --details. Swimming and gym sessions show only the list summary.",
  ]],
  ["Activities section (left menu)", [
    "Open Activities in the left menu and pick a sport (cycling, running, hiking and walking, swimming, strength) or All activities. The number beside each sport is how many workouts it has in the chosen period.",
    "Choose 1, 3, 6 or 12 months. You get the totals (workouts, time, distance, climbing), hours per month, and every workout grouped by month. Click a ride, run or hike to open the same details window as on the overview.",
    "History only goes back as far as you have downloaded it. If the page says your history starts later than the period you chose, run: .venv/bin/python scripts/backfill.py --days 365 --details",
  ]],
  ["Logging an activity by hand", [
    "Under Activities, open \"+ Log an activity by hand\". Pick the activity from the drop-down (strength, running, cycling, swimming, hiking, walking or other), the day, the minutes and how hard it felt from 1 to 10. Distance is optional.",
    "Garmin misses some sessions, strength especially. Anything you log counts toward your week and your training load, and you can delete an entry from the same list.",
  ]],
  ["Keeping it current", [
    "The page shows stored data. To refresh from Garmin, run in a terminal: .venv/bin/python main.py (add --no-collect to skip the download).",
    "Sync your watch first. If the data is old, the header says how many days behind it is.",
  ]],
  ["Words you will see", [
    "HRV: heart-rate variability, a recovery signal. Higher than usual is generally good.",
    "Baseline / usual: your own recent median, not a population average.",
    "Load: Garmin's training load per workout. Weekly load is compared with your 8-week average.",
    "Hard / easy: hard means a top-quarter effort for you or lots of time in zones 4-5. A hard day is normally followed by an easy one.",
  ]],
  ["Limits", [
    "This is a decision aid, not medical advice. If you feel ill or injured, rest regardless of what the page says.",
    "Thresholds are first guesses and will be tuned after you have used it for a while.",
  ]],
];

export default {
  id: "guide",
  title: "Guide",
  render(sec, data, state) {
    const box = el("details", { class: "guide" }, el("summary", { text: "User guide" }));
    for (const [title, paras] of SECTIONS) {
      box.append(el("h3", { text: title }), ...paras.map((t) => el("p", { text: t })));
    }
    sec.append(box);
    box.open = Boolean(state && state.guideOpen);
  },
};
