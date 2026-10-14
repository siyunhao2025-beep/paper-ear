(() => {
  document.documentElement.classList.add("js");

  const body = document.body;
  const modeButtons = [...document.querySelectorAll("[data-reader-mode]")];
  const searchInput = document.querySelector("#reader-search");
  const searchStatus = document.querySelector("#search-status");
  const searchable = [...document.querySelectorAll("[data-search]")];
  const filterButtons = [...document.querySelectorAll("[data-visual-filter]")];
  const visualCards = [...document.querySelectorAll(".visual-card")];
  const navLinks = [...document.querySelectorAll(".rail-nav a")];
  const sections = [...document.querySelectorAll(".reader-section[id]")];
  const dialog = document.querySelector("#visual-dialog");
  const dialogImage = document.querySelector("#dialog-image");
  const dialogTitle = document.querySelector("#dialog-title");
  const dialogClose = document.querySelector("#dialog-close");
  const dialogViewButtons = [...document.querySelectorAll("[data-dialog-view]")];
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let currentVisual = null;

  const safeStorage = {
    get(key) {
      try {
        return window.localStorage.getItem(key);
      } catch (_error) {
        return null;
      }
    },
    set(key, value) {
      try {
        window.localStorage.setItem(key, value);
      } catch (_error) {
        // Local file privacy modes can disable storage; reading still works.
      }
    },
  };

  function setMode(mode) {
    const valid = ["scan", "standard", "deep"].includes(mode) ? mode : "standard";
    body.dataset.mode = valid;
    modeButtons.forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.readerMode === valid));
    });
    safeStorage.set("paper-ear-reader-mode", valid);
  }

  modeButtons.forEach((button) => {
    button.addEventListener("click", () => setMode(button.dataset.readerMode));
  });
  setMode(safeStorage.get("paper-ear-reader-mode") || body.dataset.mode || "standard");

  function updateProgress() {
    const root = document.documentElement;
    const scrollable = root.scrollHeight - window.innerHeight;
    const progress = scrollable > 0 ? Math.min(100, Math.max(0, (window.scrollY / scrollable) * 100)) : 0;
    root.style.setProperty("--progress", `${progress}%`);
  }

  window.addEventListener("scroll", updateProgress, { passive: true });
  window.addEventListener("resize", updateProgress);
  updateProgress();

  if (reducedMotion || !("IntersectionObserver" in window)) {
    document.querySelectorAll(".reveal").forEach((node) => node.classList.add("is-visible"));
  } else {
    const revealObserver = new IntersectionObserver(
      (entries, observer) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { rootMargin: "0px 0px -10%", threshold: 0.08 },
    );
    document.querySelectorAll(".reveal").forEach((node) => revealObserver.observe(node));
  }

  if ("IntersectionObserver" in window && sections.length) {
    const activeObserver = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (!visible) return;
        navLinks.forEach((link) => {
          link.setAttribute("aria-current", String(link.getAttribute("href") === `#${visible.target.id}`));
        });
      },
      { rootMargin: "-18% 0px -62%", threshold: [0.05, 0.25, 0.55] },
    );
    sections.forEach((section) => activeObserver.observe(section));
  }

  function normalizeText(value) {
    return value.toLocaleLowerCase().replace(/\s+/g, " ").trim();
  }

  function runSearch() {
    const query = normalizeText(searchInput?.value || "");
    let shown = 0;
    searchable.forEach((node) => {
      const matches = !query || normalizeText(node.dataset.search || node.textContent).includes(query);
      node.dataset.searchHidden = String(!matches);
      if (matches) shown += 1;
    });
    if (searchStatus) {
      searchStatus.textContent = query ? `找到 ${shown} 个相关内容块` : "输入术语、结论、页码或图表编号";
    }
  }

  searchInput?.addEventListener("input", runSearch);

  filterButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const filter = button.dataset.visualFilter;
      filterButtons.forEach((item) => item.setAttribute("aria-pressed", String(item === button)));
      visualCards.forEach((card) => {
        card.hidden = filter !== "all" && card.dataset.kind !== filter;
      });
    });
  });

  function setDialogView(view) {
    if (!currentVisual || !dialogImage) return;
    const useSource = view === "source";
    dialogImage.src = useSource ? currentVisual.source : currentVisual.crop;
    dialogImage.alt = useSource ? `${currentVisual.alt}，PDF 原页定位` : currentVisual.alt;
    dialogViewButtons.forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.dialogView === view));
    });
  }

  document.querySelectorAll("[data-open-visual]").forEach((button) => {
    button.addEventListener("click", () => {
      currentVisual = {
        crop: button.dataset.crop,
        source: button.dataset.source,
        alt: button.dataset.alt || "论文视觉证据",
        title: button.dataset.title || "视觉证据",
      };
      if (dialogTitle) dialogTitle.textContent = currentVisual.title;
      setDialogView(button.dataset.initialView || "crop");
      if (typeof dialog?.showModal === "function") {
        dialog.showModal();
      }
    });
  });

  dialogViewButtons.forEach((button) => {
    button.addEventListener("click", () => setDialogView(button.dataset.dialogView));
  });
  dialogClose?.addEventListener("click", () => dialog.close());
  dialog?.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });

  document.querySelectorAll("[data-bookmark]").forEach((button) => {
    const key = `paper-ear-bookmark:${button.dataset.bookmark}`;
    const refresh = () => {
      const saved = safeStorage.get(key) === "1";
      button.setAttribute("aria-pressed", String(saved));
      button.textContent = saved ? "已收藏" : "收藏证据";
    };
    refresh();
    button.addEventListener("click", () => {
      safeStorage.set(key, safeStorage.get(key) === "1" ? "0" : "1");
      refresh();
    });
  });

  document.querySelectorAll("[data-copy]").forEach((button) => {
    button.addEventListener("click", async () => {
      const original = button.textContent;
      try {
        await navigator.clipboard.writeText(button.dataset.copy);
        button.textContent = "已复制";
      } catch (_error) {
        button.textContent = "复制失败";
      }
      window.setTimeout(() => {
        button.textContent = original;
      }, 1400);
    });
  });
})();
