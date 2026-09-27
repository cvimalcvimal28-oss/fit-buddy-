(() => {
  document.querySelectorAll("[data-password-toggle]").forEach((toggle) => {
    if (!(toggle instanceof HTMLButtonElement)) return;
    const inputId = toggle.getAttribute("aria-controls");
    const input = inputId ? document.getElementById(inputId) : null;
    const label = toggle.querySelector("span");
    if (!(input instanceof HTMLInputElement) || !label) return;

    toggle.addEventListener("click", () => {
      const shouldShow = input.type === "password";
      input.type = shouldShow ? "text" : "password";
      toggle.setAttribute("aria-pressed", String(shouldShow));
      toggle.setAttribute("aria-label", `${shouldShow ? "Hide" : "Show"} ${input.labels?.[0]?.textContent?.toLowerCase() ?? "password"}`);
      label.textContent = shouldShow ? "Hide" : "Show";
    });
  });

  const planForm = document.querySelector("[data-plan-form]");

  if (planForm instanceof HTMLFormElement) {
    const requiredFields = Array.from(planForm.querySelectorAll("[required]"));
    const progressMessage = document.querySelector("[data-form-progress]");
    const submitButton = planForm.querySelector("[data-submit-button]");
    const goalSelect = planForm.querySelector("#fitness_goal");
    const goalHint = planForm.querySelector("[data-goal-hint]");
    const goalDescriptions = {
      "Weight Loss": "Build a steady routine with movement that feels sustainable.",
      "Muscle Gain": "Combine focused strength work with time to recover.",
      "General Wellness": "Build a balanced week of strength, movement, and recovery."
    };

    const updateProgress = () => {
      const completed = requiredFields.filter((field) => field.value.trim() !== "").length;
      const total = requiredFields.length;

      if (progressMessage) {
        progressMessage.textContent = completed === total
          ? "Your details are in. Your plan is ready to build."
          : `${completed} of ${total} details complete.`;
      }
    };

    requiredFields.forEach((field) => {
      field.addEventListener("input", updateProgress);
      field.addEventListener("change", updateProgress);
    });

    if (goalSelect instanceof HTMLSelectElement && goalHint) {
      const updateGoalHint = () => {
        goalHint.textContent = goalDescriptions[goalSelect.value] ?? goalDescriptions["General Wellness"];
      };
      goalSelect.addEventListener("change", updateGoalHint);
      updateGoalHint();
    }

    planForm.addEventListener("submit", () => {
      if (submitButton instanceof HTMLButtonElement) {
        submitButton.disabled = true;
        submitButton.setAttribute("aria-busy", "true");
        const buttonText = submitButton.querySelector("span");
        if (buttonText) buttonText.textContent = "Building your plan…";
      }
    });

    updateProgress();
  }

  document.querySelectorAll("[data-workout-progress]").forEach((progress) => {
    if (!(progress instanceof HTMLElement)) return;

    const planKey = progress.dataset.planKey;
    const totalDays = Number(progress.dataset.totalDays);
    const dayEntries = Array.from(document.querySelectorAll("[data-workout-day]"));
    const countLabel = progress.querySelector("[data-progress-count]");
    const percentLabel = progress.querySelector("[data-progress-percent]");
    const bar = progress.querySelector("[data-progress-bar]");
    if (!planKey || !Number.isInteger(totalDays) || totalDays < 1) return;

    let completedDays = [];
    try {
      const stored = window.localStorage.getItem(planKey);
      const parsed = stored ? JSON.parse(stored) : [];
      if (Array.isArray(parsed)) {
        completedDays = parsed.filter((day) => Number.isInteger(day) && day > 0 && day <= totalDays);
      }
    } catch (error) {
      console.error("Unable to load saved workout progress.", error);
    }

    const updateProgress = () => {
      const completedCount = completedDays.length;
      const percent = Math.round((completedCount / totalDays) * 100);
      if (countLabel) countLabel.textContent = `${completedCount} of ${totalDays} sessions`;
      if (percentLabel) percentLabel.textContent = `${percent}%`;
      if (bar instanceof HTMLElement) bar.style.width = `${percent}%`;
    };

    const saveProgress = () => {
      try {
        window.localStorage.setItem(planKey, JSON.stringify(completedDays));
      } catch (error) {
        console.error("Unable to save workout progress.", error);
      }
    };

    dayEntries.forEach((entry) => {
      if (!(entry instanceof HTMLElement)) return;
      const dayNumber = Number(entry.dataset.workoutDay);
      const button = entry.querySelector("[data-complete-day]");
      if (!(button instanceof HTMLButtonElement) || !Number.isInteger(dayNumber)) return;

      const isComplete = completedDays.includes(dayNumber);
      entry.classList.toggle("is-complete", isComplete);
      button.setAttribute("aria-pressed", String(isComplete));
      button.setAttribute("aria-label", `Mark Day ${dayNumber} ${isComplete ? "incomplete" : "complete"}`);

      button.addEventListener("click", () => {
        if (completedDays.includes(dayNumber)) {
          completedDays = completedDays.filter((day) => day !== dayNumber);
        } else {
          completedDays = [...completedDays, dayNumber];
        }
        const nowComplete = completedDays.includes(dayNumber);
        entry.classList.toggle("is-complete", nowComplete);
        button.setAttribute("aria-pressed", String(nowComplete));
        button.setAttribute("aria-label", `Mark Day ${dayNumber} ${nowComplete ? "incomplete" : "complete"}`);
        saveProgress();
        updateProgress();
      });
    });

    updateProgress();
  });
})();
