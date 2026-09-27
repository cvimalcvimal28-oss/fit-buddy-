(() => {
  const STORAGE_KEYS = {
    plan: "fitbuddy-static-plan-v1",
    feedback: "fitbuddy-static-feedback-v1",
    progress: "fitbuddy-static-progress-v1"
  };
  const form = document.querySelector("#plan-form");
  const planPanel = document.querySelector("#plan-panel");
  const workoutDays = document.querySelector("#workout-days");
  const planSummary = document.querySelector("#plan-summary");
  const status = document.querySelector("#form-status");
  const goalSelect = document.querySelector("#fitness_goal");
  const goalHint = document.querySelector("#goal-hint");
  const goalHints = {
    "Weight Loss": "Build a steady routine with movement that feels sustainable.",
    "Muscle Gain": "Combine focused strength work with time to recover.",
    "General Wellness": "Build a balanced week of strength, movement, and recovery."
  };
  const volume = {
    Low: { strength: "2 rounds · 8–10 reps", cardio: "20 minutes at a conversational pace" },
    Medium: { strength: "3 rounds · 10–12 reps", cardio: "25 minutes at a steady pace" },
    High: { strength: "3 rounds · 8–12 controlled reps", cardio: "30 minutes at a challenging, comfortable pace" }
  };
  const workouts = {
    "Weight Loss": [
      ["Full-body circuit", ["Chair squats", "Incline push-ups", "Glute bridges", "Standing marches"]],
      ["Steady cardio", ["Brisk walk", "Easy cycling", "Low-impact dance"]],
      ["Strength & balance", ["Reverse lunges", "Wall push-ups", "Bird dogs", "Calf raises"]],
      ["Mobility reset", ["Gentle hip mobility", "Shoulder circles", "Easy recovery walk"]],
      ["Full-body circuit", ["Step-backs", "Knee push-ups", "Hip hinges", "Dead bugs"]],
      ["Active recovery", ["Comfortable walk", "Full-body stretch"]],
      ["Rest day", ["Take a full rest or enjoy a relaxed walk"]]
    ],
    "Muscle Gain": [
      ["Lower-body strength", ["Squats", "Glute bridges", "Reverse lunges", "Calf raises"]],
      ["Upper-body strength", ["Incline push-ups", "Backpack rows", "Shoulder taps", "Wall slides"]],
      ["Recovery & mobility", ["Easy walk", "Gentle hip and shoulder mobility"]],
      ["Lower-body strength", ["Hip hinges", "Split squats", "Glute bridges", "Calf raises"]],
      ["Upper-body & core", ["Incline push-ups", "Backpack rows", "Dead bugs", "Bird dogs"]],
      ["Active recovery", ["Easy cycling or walking", "Light full-body stretching"]],
      ["Rest day", ["Take a full rest and let your body recover"]]
    ],
    "General Wellness": [
      ["Full-body strength", ["Chair squats", "Wall push-ups", "Glute bridges", "Bird dogs"]],
      ["Easy cardio", ["Brisk walk", "Easy cycling", "Low-impact dance"]],
      ["Mobility & balance", ["Single-leg balance", "Hip mobility", "Shoulder circles"]],
      ["Rest & reset", ["Optional relaxed walk", "Gentle stretching"]],
      ["Full-body strength", ["Step-backs", "Incline push-ups", "Hip hinges", "Dead bugs"]],
      ["Cardio & movement", ["Walk, cycle, or dance at a comfortable pace"]],
      ["Rest day", ["Take a full rest or do what feels restorative"]]
    ]
  };

  function readStorage(key) {
    try {
      const value = window.localStorage.getItem(key);
      return value ? JSON.parse(value) : null;
    } catch (error) {
      console.warn("FitBuddy could not read saved browser data.", error);
      return null;
    }
  }

  function saveStorage(key, value) {
    try {
      window.localStorage.setItem(key, JSON.stringify(value));
      return true;
    } catch (error) {
      console.warn("FitBuddy could not save browser data.", error);
      return false;
    }
  }

  function makePlan(goal, intensity) {
    const planDays = workouts[goal];
    const effort = volume[intensity];
    return {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      goal,
      intensity,
      tip: goal === "Muscle Gain"
        ? "Include a source of protein in regular meals, drink water through the day, and give your muscles time to recover."
        : goal === "Weight Loss"
          ? "Aim for regular, balanced meals and a pace you can sustain. Rest and sleep are part of a healthy routine too."
          : "Choose a variety of nourishing foods, drink water when thirsty, and protect time for sleep and rest.",
      days: planDays.map(([focus, exercises], index) => {
        const rest = /rest|recovery|mobility/i.test(focus);
        return {
          day: `Day ${index + 1}`,
          focus,
          warm_up: rest ? "Start gently and keep the movement comfortable." : "Begin with 5 minutes of easy movement, then warm up the joints you'll use.",
          main_workout: rest
            ? exercises
            : [...exercises.map((exercise) => `${exercise} — ${effort.strength}`), `Finish with ${effort.cardio} of easy movement.`],
          cooldown: rest ? "Pause, breathe, and rest whenever you need to." : "Cool down with a few minutes of easy movement and a comfortable stretch."
        };
      })
    };
  }

  function addText(parent, tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    element.textContent = text;
    parent.append(element);
    return element;
  }

  function updateProgress(plan) {
    const stored = readStorage(STORAGE_KEYS.progress);
    const complete = stored && stored.planId === plan.id && Array.isArray(stored.days)
      ? stored.days.filter((day) => Number.isInteger(day) && day >= 1 && day <= 7)
      : [];
    const count = new Set(complete).size;
    document.querySelector("#progress-count").textContent = `${count} of 7 sessions`;
    document.querySelector("#progress-percent").textContent = `${Math.round(count / 7 * 100)}%`;
    document.querySelector("#progress-bar").style.width = `${Math.round(count / 7 * 100)}%`;
  }

  function renderPlan(plan, name = "") {
    if (!plan || typeof plan.id !== "string" || !Array.isArray(plan.days) || plan.days.length !== 7
      || !volume[plan.intensity] || !workouts[plan.goal] || typeof plan.tip !== "string"
      || !plan.days.every((day, index) => day && day.day === `Day ${index + 1}`
        && typeof day.focus === "string" && typeof day.warm_up === "string"
        && Array.isArray(day.main_workout) && day.main_workout.every((item) => typeof item === "string")
        && typeof day.cooldown === "string")) return false;
    workoutDays.replaceChildren();
    planSummary.replaceChildren();
    const displayName = name.trim();
    const title = document.querySelector("#plan-title");
    title.replaceChildren(document.createTextNode("Let's get"));
    title.append(document.createElement("br"));
    addText(title, "em", "", displayName ? `moving, ${displayName}.` : "moving.");
    document.querySelector("#plan-intro").textContent = `A practical ${plan.intensity.toLowerCase()}-pace week, shaped around ${plan.goal.toLowerCase()}.`;
    [
      ["7 days", "A week to start"],
      [plan.goal, "Your goal"],
      [plan.intensity, "Starting pace"],
      ["At your pace", "Make it yours"]
    ].forEach(([value, label]) => {
      const stat = document.createElement("div");
      stat.className = "stat";
      addText(stat, "div", "num", value);
      addText(stat, "div", "label", label);
      planSummary.append(stat);
    });
    document.querySelector("#recovery-tip").textContent = plan.tip;

    plan.days.forEach((day, index) => {
      const entry = document.createElement("article");
      entry.className = "day-entry";
      entry.dataset.workoutDay = String(index + 1);
      const rail = document.createElement("div");
      rail.className = "day-rail";
      addText(rail, "div", "day-num", String(index + 1).padStart(2, "0"));
      const doneButton = document.createElement("button");
      doneButton.className = "day-complete";
      doneButton.type = "button";
      doneButton.setAttribute("aria-pressed", "false");
      doneButton.setAttribute("aria-label", `Mark ${day.day} complete`);
      addText(doneButton, "span", "", "✓").setAttribute("aria-hidden", "true");
      addText(doneButton, "span", "complete-label", "DONE");
      rail.append(doneButton);
      const body = document.createElement("div");
      body.className = "day-body";
      const heading = document.createElement("div");
      heading.className = "day-heading";
      const title = document.createElement("div");
      addText(title, "span", "day-kicker", day.day);
      addText(title, "h3", "day-focus", day.focus);
      heading.append(title);
      const tag = document.createElement("span");
      tag.className = "day-tag";
      tag.textContent = /rest|recovery|mobility/i.test(day.focus) ? "RECOVERY" : "TRAINING";
      heading.append(tag);
      body.append(heading);
      const details = document.createElement("div");
      details.className = "session-details";
      const warmUp = document.createElement("div");
      warmUp.className = "session-stage";
      addText(warmUp, "span", "stage-label", "Warm up");
      addText(warmUp, "p", "", day.warm_up);
      const mainWorkout = document.createElement("div");
      mainWorkout.className = "session-stage";
      addText(mainWorkout, "span", "stage-label", "Main workout");
      const exerciseList = document.createElement("ul");
      day.main_workout.forEach((exercise) => addText(exerciseList, "li", "", exercise));
      mainWorkout.append(exerciseList);
      const coolDown = document.createElement("div");
      coolDown.className = "session-stage";
      addText(coolDown, "span", "stage-label", "Cool down");
      addText(coolDown, "p", "", day.cooldown);
      details.append(warmUp, mainWorkout, coolDown);
      body.append(details);
      entry.append(rail, body);
      workoutDays.append(entry);

      const saved = readStorage(STORAGE_KEYS.progress);
      const completed = saved && saved.planId === plan.id && Array.isArray(saved.days) && saved.days.includes(index + 1);
      entry.classList.toggle("is-complete", Boolean(completed));
      doneButton.setAttribute("aria-pressed", String(Boolean(completed)));
      doneButton.setAttribute("aria-label", `Mark ${day.day} ${completed ? "incomplete" : "complete"}`);
      doneButton.addEventListener("click", () => {
        const current = readStorage(STORAGE_KEYS.progress);
        const done = new Set(current && current.planId === plan.id && Array.isArray(current.days) ? current.days : []);
        if (done.has(index + 1)) done.delete(index + 1);
        else done.add(index + 1);
        const isDone = done.has(index + 1);
        entry.classList.toggle("is-complete", isDone);
        doneButton.setAttribute("aria-pressed", String(isDone));
        doneButton.setAttribute("aria-label", `Mark ${day.day} ${isDone ? "incomplete" : "complete"}`);
        saveStorage(STORAGE_KEYS.progress, { planId: plan.id, days: [...done] });
        updateProgress(plan);
      });
    });
    planPanel.hidden = false;
    updateProgress(plan);
    return true;
  }

  if (goalSelect && goalHint) {
    goalSelect.addEventListener("change", () => {
      goalHint.textContent = goalHints[goalSelect.value] || goalHints["General Wellness"];
    });
  }

  if (form && planPanel) {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      const data = new FormData(form);
      const plan = makePlan(String(data.get("fitness_goal")), String(data.get("workout_intensity")));
      renderPlan(plan, String(data.get("name") || ""));
      if (saveStorage(STORAGE_KEYS.plan, plan)) {
        status.textContent = "Your plan is ready. It is saved in this browser.";
      } else {
        status.textContent = "Your plan is ready for this visit. Browser storage is unavailable, so it could not be saved.";
      }
      planPanel.scrollIntoView({ behavior: "smooth", block: "start" });
    });

    const savedPlan = readStorage(STORAGE_KEYS.plan);
    if (savedPlan) {
      if (renderPlan(savedPlan)) {
        goalSelect.value = savedPlan.goal;
        document.querySelector("#workout_intensity").value = savedPlan.intensity;
        goalSelect.dispatchEvent(new Event("change"));
        status.textContent = "Your saved plan is ready. It stays in this browser.";
      } else {
        status.textContent = "A saved plan could not be read. Build a new plan to continue.";
      }
    }
  }

  document.querySelector("#print-plan")?.addEventListener("click", () => window.print());
  document.querySelector("#edit-plan")?.addEventListener("click", () => {
    document.querySelector("#builder").scrollIntoView({ behavior: "smooth", block: "center" });
    document.querySelector("#fitness_goal").focus({ preventScroll: true });
  });

  const feedbackForm = document.querySelector("#feedback-form");
  const feedbackStatus = document.querySelector("#feedback-status");
  if (feedbackForm && feedbackStatus) {
    const savedFeedback = readStorage(STORAGE_KEYS.feedback);
    if (savedFeedback && typeof savedFeedback.note === "string") {
      feedbackForm.elements.feedback.value = savedFeedback.note;
      feedbackStatus.textContent = "Your previous note is saved on this device.";
    }
    feedbackForm.addEventListener("submit", (event) => {
      event.preventDefault();
      const note = String(new FormData(feedbackForm).get("feedback") || "").trim();
      if (!note) {
        feedbackStatus.textContent = "Add a note before saving your feedback.";
        feedbackForm.elements.feedback.focus();
        return;
      }
      feedbackStatus.textContent = saveStorage(STORAGE_KEYS.feedback, { note, savedAt: new Date().toISOString() })
        ? "Saved on this device only. It was not sent to FitBuddy."
        : "Browser storage is unavailable, so your note could not be saved.";
    });
  }
})();
