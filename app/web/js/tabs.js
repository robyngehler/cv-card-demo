const TAB_KEY = "cv-card-demo.active-tab";

export function initTabs(store) {
  const buttons = Array.from(document.querySelectorAll(".tab-button"));
  const panels = Array.from(document.querySelectorAll(".tab-panel"));
  const remembered = window.localStorage.getItem(TAB_KEY);
  if (remembered) {
    store.patch("ui.activeTab", remembered);
  }

  function applyActiveTab(tabName) {
    for (const button of buttons) {
      button.classList.toggle("active", button.dataset.tab === tabName);
    }
    for (const panel of panels) {
      panel.classList.toggle("active", panel.id === `tab-${tabName}`);
    }
  }

  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      const nextTab = button.dataset.tab;
      if (!nextTab) {
        return;
      }
      store.patch("ui.activeTab", nextTab);
      store.pushEvent("tab", `Switched to ${nextTab}`);
      window.localStorage.setItem(TAB_KEY, nextTab);
    });
  });

  store.subscribe((state) => {
    applyActiveTab(state.ui.activeTab || "questionnaire");
  });
}
