(() => {
  const exchanges = [
    {
      q: "How many customers do I have?",
      a: "You have <strong>938 customers</strong> (938 active).",
    },
    {
      q: "Who owes me money?",
      a: "<strong>14 open invoices</strong> totaling <strong>$6,240.00</strong> due.<br/>Top: Joshua Hernandez $200, Oak Ridge HOA $1,150, Marina Cafe $480.",
    },
    {
      q: "How much Alpine did we use this week?",
      a: "Last 7 days across 73 jobs:<br/><strong>Alpine WSG: 11.25 gallons</strong> (28 jobs). Also Bifen I/T 57 gal, Taurus SC 24 gal.",
    },
    {
      q: "Who did the most jobs?",
      a: "Top producer: <strong>Tony Bolanos</strong> on Route #2 with <strong>41 completed jobs</strong> this month.",
    },
    {
      q: "How is business doing?",
      a: "Last 30 days: <strong>363 of 394 jobs completed</strong>. Production value <strong>$40,321.50</strong> (planned $41,251.50).",
    },
  ];

  const stream = document.getElementById("chat-stream");
  if (stream) {
    let index = 0;
    const wait = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));

    const showTyping = () => {
      const el = document.createElement("div");
      el.className = "bubble typing enter";
      el.setAttribute("aria-label", "Thinking");
      el.innerHTML = "<span></span><span></span><span></span>";
      stream.appendChild(el);
      return el;
    };

    const addBubble = (role, html) => {
      const el = document.createElement("div");
      el.className = `bubble ${role} enter`;
      el.innerHTML = html;
      stream.appendChild(el);
      return el;
    };

    const runLoop = async () => {
      while (true) {
        const item = exchanges[index % exchanges.length];
        stream.innerHTML = "";
        stream.classList.remove("fade-out");

        await wait(350);
        addBubble("you", item.q);

        const typing = showTyping();
        await wait(1100);
        typing.remove();
        addBubble("ai", item.a);

        await wait(3200);
        stream.classList.add("fade-out");
        await wait(400);
        index += 1;
      }
    };

    runLoop();
  }

  const tabs = document.querySelectorAll(".client-tab");
  const panels = document.querySelectorAll(".client-panel");

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const key = tab.dataset.client;
      tabs.forEach((t) => t.classList.toggle("active", t === tab));
      panels.forEach((panel) => {
        panel.classList.toggle("active", panel.dataset.panel === key);
      });
    });
  });

  document.querySelectorAll("[data-copy]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const sel = btn.getAttribute("data-copy");
      const target = sel ? document.querySelector(sel) : btn.closest(".copy-block")?.querySelector("code");
      if (!target) return;
      const text = target.textContent || "";
      try {
        await navigator.clipboard.writeText(text);
        const original = btn.textContent;
        btn.textContent = "Copied";
        window.setTimeout(() => {
          btn.textContent = original;
        }, 1400);
      } catch {
        btn.textContent = "Select text and copy";
      }
    });
  });

  const questions = [
    "How many customers do I have?",
    "Who owes me money?",
    "How much did we make this month?",
    "How is business doing?",
    "How much product was used this week?",
    "What chemicals do we carry?",
    "Who are my technicians?",
    "Who did the most jobs?",
    "What is on the schedule this week?",
    "Which route is busiest?",
    "Do I have a customer named Hernandez?",
    "Give me a Monday morning briefing",
  ];

  const askRoot = document.getElementById("ask-simple");
  const askQ = document.getElementById("ask-q");
  const askCount = document.getElementById("ask-count");
  const askToast = document.getElementById("ask-toast");

  if (askRoot && askQ && askCount) {
    let i = 0;
    let toastTimer;

    const render = () => {
      askQ.classList.add("swap");
      window.setTimeout(() => {
        askQ.textContent = questions[i];
        askCount.textContent = `${i + 1} / ${questions.length}`;
        askQ.classList.remove("swap");
      }, 120);
    };

    document.getElementById("ask-next")?.addEventListener("click", () => {
      i = (i + 1) % questions.length;
      render();
    });

    document.getElementById("ask-copy")?.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(questions[i]);
        if (askToast) {
          askToast.hidden = false;
          askToast.textContent = "Copied";
          window.clearTimeout(toastTimer);
          toastTimer = window.setTimeout(() => {
            askToast.hidden = true;
          }, 1400);
        }
      } catch {
        if (askToast) {
          askToast.hidden = false;
          askToast.textContent = "Select the text and copy";
        }
      }
    });

    askQ.textContent = questions[0];
    askCount.textContent = `1 / ${questions.length}`;
  }
})();
