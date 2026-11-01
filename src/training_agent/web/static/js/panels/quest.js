// Daily quest: placeholder until the planner (roadmap phases 4-5) produces today's session.
import { el } from "../util.js";

export default {
  id: "quest",
  title: "Daily quest",
  render(sec) {
    sec.append(el("h2", { text: "Daily quest" }),
      el("div", { class: "quest" },
        el("div", { class: "big", text: "Awaiting the agent" }),
        el("div", { class: "locked", text:
          "Today's session and the reason for it will appear here once the planner is built. " +
          "For now, read your status window and trends." })));
  },
};
