(() => {
  const exchanges = [
    {
      q: "How many customers do I have?",
      a: "You have <strong>1,842 customers</strong> in FieldRoutes (status sample from recent records).",
    },
    {
      q: "Who owes me money?",
      a: "<strong>22 customers</strong> owe a total of <strong>$8,910.00</strong>.<br/>Top: Riverside HOA $1,420, Maya Chen $640, Oak Lawn LLC $510.",
    },
    {
      q: "What's on the schedule this week?",
      a: "Schedule next 7 days: <strong>186 appointments</strong> across <strong>41 routes</strong>.",
    },
    {
      q: "Who are my technicians?",
      a: "You have <strong>9 technicians</strong>: Tony Bolanos; Sam Ortiz; Priya Shah; …",
    },
    {
      q: "How are my routes doing?",
      a: "Route load this week: <strong>Tony Bolanos: 12 routes</strong>; Sam Ortiz: 10; Priya Shah: 8.",
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
    "How are my routes doing?",
    "Do I have a customer named Hernandez?",
    "Which tech has the most routes this week?",
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
