/* Module 01 — reading progress, contents spy, quiz, live timing panel. */
(function () {
  "use strict";

  /* ------------------------------------------------- progress + contents -- */

  function readingPosition() {
    var bar = document.getElementById("progress");
    var links = Array.prototype.slice.call(document.querySelectorAll("[data-spy]"));
    var targets = links
      .map(function (a) { return document.querySelector(a.getAttribute("href")); })
      .filter(Boolean);
    var ticking = false;

    function update() {
      ticking = false;
      var root = document.documentElement;
      var scrolled = window.pageYOffset || root.scrollTop;
      var height = root.scrollHeight - root.clientHeight;

      if (bar) {
        bar.style.width = (height > 0 ? Math.min(scrolled / height, 1) * 100 : 0) + "%";
      }
      if (!targets.length) return;

      var line = scrolled + 160;
      var current = targets[0];
      targets.forEach(function (el) {
        if (el.offsetTop <= line) current = el;
      });

      links.forEach(function (a) {
        a.classList.toggle("is-current", a.getAttribute("href") === "#" + current.id);
      });
    }

    function request() {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(update);
    }

    window.addEventListener("scroll", request, { passive: true });
    window.addEventListener("resize", request);
    update();
  }

  /* --------------------------------------------------------------- quiz -- */

  function quiz() {
    var form = document.getElementById("quiz");
    if (!form) return;

    var groups = Array.prototype.slice.call(form.querySelectorAll(".q"));
    var scoreText = document.getElementById("score-text");
    var scoreFill = document.getElementById("score-fill");
    var answered = 0;
    var correct = 0;

    groups.forEach(function (group) {
      var answer = group.getAttribute("data-answer");
      var feedback = group.querySelector(".feedback");

      group.addEventListener("change", function (event) {
        var input = event.target;
        if (!input || input.type !== "radio") return;

        var labels = Array.prototype.slice.call(group.querySelectorAll(".opt"));
        var chosen = input.value;

        labels.forEach(function (label) {
          var option = label.querySelector("input");
          label.classList.add("is-locked");
          if (option.value === answer) label.classList.add("is-correct");
        });

        var isRight = chosen === answer;
        if (!isRight) input.closest(".opt").classList.add("is-wrong");

        if (feedback) {
          feedback.hidden = false;
          feedback.setAttribute("data-state", isRight ? "correct" : "wrong");
        }

        group.querySelectorAll("input").forEach(function (i) { i.disabled = true; });

        answered += 1;
        if (isRight) correct += 1;

        if (scoreText) {
          scoreText.textContent =
            answered + " of " + groups.length + " answered" +
            (answered > 1 ? " · " + correct + " correct" : "");
        }
        if (scoreFill) {
          scoreFill.style.width = (answered / groups.length) * 100 + "%";
        }
      });
    });
  }

  /* ----------------------------------------------------- timing panel ---- */

  function timing() {
    var button = document.getElementById("measure-btn");
    var note = document.getElementById("m-note");
    if (!button) return;

    var fields = {
      dns: document.getElementById("m-dns"),
      tcp: document.getElementById("m-tcp"),
      tls: document.getElementById("m-tls"),
      ttfb: document.getElementById("m-ttfb"),
      total: document.getElementById("m-total")
    };

    function fmt(ms) {
      if (ms === null || ms === undefined || !isFinite(ms) || ms < 0) return "—";
      if (ms === 0) return "0 ms";
      if (ms < 1) return "<1 ms";
      return ms.toFixed(1) + " ms";
    }

    function paint(entry) {
      if (!entry) return false;
      var tls = entry.secureConnectionStart > 0
        ? entry.connectEnd - entry.secureConnectionStart
        : null;

      fields.dns.textContent = fmt(entry.domainLookupEnd - entry.domainLookupStart);
      fields.tcp.textContent = fmt(entry.connectEnd - entry.connectStart);
      fields.tls.textContent = fmt(tls);
      fields.ttfb.textContent = fmt(entry.responseStart - entry.requestStart);
      fields.total.textContent = fmt(entry.duration);
      return true;
    }

    var nav = window.performance && performance.getEntriesByType
      ? performance.getEntriesByType("navigation")[0]
      : null;

    if (!nav) {
      button.hidden = true;
      if (note) note.textContent = "This browser does not expose navigation timing, so the panel stays empty.";
      return;
    }
    paint(nav);

    button.addEventListener("click", function () {
      button.disabled = true;
      if (note) note.textContent = "Measuring a fresh request…";

      var url = window.location.pathname + "?probe=" + Date.now();

      /* The body must be consumed before the resource-timing entry exists,
         otherwise the entry lookup below races the fetch and finds nothing. */
      fetch(url, { cache: "no-store" })
        .then(function (response) { return response.text(); })
        .then(function () {
          var entries = (performance.getEntriesByType("resource") || []).filter(function (e) {
            return e.name.indexOf("probe=") !== -1;
          });
          var latest = entries[entries.length - 1];
          if (latest) paint(latest);
          if (note) {
            note.textContent = latest
              ? "A cache-busted request timed in your browser. Warm connections show <1 ms for DNS and TCP — connection reuse, not a rounding error."
              : "The request completed but this browser recorded no timing for it, so the panel keeps the load-time numbers.";
          }
        })
        .catch(function () {
          if (note) note.textContent = "The probe request failed, so there is nothing new to time. Serve this page over http rather than opening the file directly.";
        })
        .then(function () { button.disabled = false; });
    });
  }

  function init() {
    readingPosition();
    quiz();
    timing();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
