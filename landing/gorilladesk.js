(() => {
  const exchanges = [
    {
      q: "How many customers do I have?",
      a: "You have <strong>1,842 active customers</strong> in GorillaDesk (1,610 active, 180 leads, 52 inactive).",
    },
    {
      q: "Who owes me money?",
      a: "<strong>18 open invoices</strong> total <strong>$6,420.00</strong> due.<br/>Top: Riverside HOA $1,200, Maya Chen $480, Oak Lawn LLC $390.",
    },
    {
      q: "What's on the schedule this week?",
      a: "<strong>142 jobs</strong> from Mon–Sun (98 Scheduled, 30 Completed, 14 Canceled).",
    },
    {
      q: "Who are my technicians?",
      a: "<strong>11 users</strong> (8 technician, 3 admin).<br/>Team: Tony Bolanos, Sam Ortiz, Priya Shah…",
    },
    {
      q: "How's money this month?",
      a: "Invoiced <strong>$35,200</strong> · Collected <strong>$28,900</strong> · Still due <strong>$4,110</strong>.",
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

  document.querySelectorAll("[data-copy]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const sel = btn.getAttribute("data-copy");
      const target = sel
        ? document.querySelector(sel)
        : btn.closest(".copy-block")?.querySelector("code");
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
    "What is on the schedule this week?",
    "Who are my technicians?",
    "How's money this month?",
    "Do I have a customer named Hernandez?",
    "What services do we offer?",
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
