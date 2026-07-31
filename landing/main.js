(() => {
  document.querySelectorAll("[data-copy]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const text = btn.getAttribute("data-copy") || "";
      try {
        await navigator.clipboard.writeText(text);
        const original = btn.textContent;
        btn.textContent = "Copied";
        window.setTimeout(() => {
          btn.textContent = original;
        }, 1200);
      } catch {
        btn.textContent = "Copy failed";
      }
    });
  });

  const nodes = document.querySelectorAll(".dir-row, .works, .finale, .section-head, .term");
  if ("IntersectionObserver" in window && nodes.length) {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("in-view");
          io.unobserve(entry.target);
        });
      },
      { threshold: 0.14 },
    );
    nodes.forEach((node) => {
      node.classList.add("await-in");
      io.observe(node);
    });
  }
})();
