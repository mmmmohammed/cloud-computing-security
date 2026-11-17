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

    /* Runs directly in the scroll handler rather than through
       requestAnimationFrame: rAF is suspended in background tabs and on some
       low-power scroll paths, which left the rail and progress bar frozen. */
    function update() {
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

    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
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

  /* ------------------------------------------------ sortable data tables -- */

  function sortableTables() {
    var tables = document.querySelectorAll('table[data-sortable]');
    if (!tables.length) return;

    Array.prototype.forEach.call(tables, function (table) {
      var body = table.tBodies[0];
      if (!body) return;

      var headers = Array.prototype.slice.call(table.querySelectorAll('th[data-key]'));

      headers.forEach(function (th) {
        var button = th.querySelector('button');
        if (!button) return;

        button.addEventListener('click', function () {
          var index = Array.prototype.indexOf.call(th.parentNode.children, th);
          var numeric = th.hasAttribute('data-numeric');
          var ascending = th.getAttribute('aria-sort') !== 'ascending';

          headers.forEach(function (other) { other.removeAttribute('aria-sort'); });
          th.setAttribute('aria-sort', ascending ? 'ascending' : 'descending');

          var rows = Array.prototype.slice.call(body.rows);
          rows.sort(function (a, b) {
            var av = cellValue(a.cells[index]);
            var bv = cellValue(b.cells[index]);
            if (numeric) {
              var an = parseFloat(av);
              var bn = parseFloat(bv);
              if (isNaN(an)) an = Infinity;
              if (isNaN(bn)) bn = Infinity;
              return ascending ? an - bn : bn - an;
            }
            return ascending ? String(av).localeCompare(bv) : String(bv).localeCompare(av);
          });

          rows.forEach(function (row) { body.appendChild(row); });
        });
      });
    });

    function cellValue(cell) {
      if (!cell) return '';
      return cell.hasAttribute('data-v') ? cell.getAttribute('data-v') : cell.textContent.trim();
    }
  }

  /* ------------------------------------------- responsibility matrix focus -- */

  function stackFocus() {
    var fig = document.getElementById('stackfig');
    if (!fig) return;

    var summary = document.getElementById('stack-summary');
    var buttons = Array.prototype.slice.call(fig.querySelectorAll('button[data-focus]'));
    var rows = Array.prototype.slice.call(fig.querySelectorAll('tr[data-layer]'));
    var names = { onprem: 'On-premises', iaas: 'IaaS', paas: 'PaaS', saas: 'SaaS' };

    function apply(model) {
      var active = fig.getAttribute('data-focus') === model ? 'none' : model;
      fig.setAttribute('data-focus', active);

      buttons.forEach(function (button) {
        button.setAttribute('aria-pressed', String(button.getAttribute('data-focus') === active));
      });

      if (!summary) return;
      if (active === 'none') {
        summary.textContent = 'Pick a model above to see what it leaves you owning.';
        return;
      }

      var mine = rows.filter(function (row) {
        var cell = row.querySelector('td[data-col="' + active + '"]');
        return cell && cell.getAttribute('data-owner') === 'you';
      }).map(function (row) {
        return row.querySelector('th').textContent.trim().toLowerCase();
      });

      var total = rows.length;
      summary.textContent = names[active] + ': the provider manages ' + (total - mine.length) +
        ' of ' + total + ' layers. You still own ' + mine.length + ' — ' + mine.join(', ') + '.';
    }

    buttons.forEach(function (button) {
      button.addEventListener('click', function () {
        apply(button.getAttribute('data-focus'));
      });
    });
  }

  /* --------------------------------------------------------- panels ----- */

  /* One switcher for any figure whose buttons reveal one panel at a time.
     `key` is the data attribute on the button whose value names the panel. */
  function switchPanels(boxId, key) {
    var box = document.getElementById(boxId);
    if (!box) return;

    var buttons = Array.prototype.slice.call(box.querySelectorAll('button[' + key + ']'));
    var panels = Array.prototype.slice.call(box.querySelectorAll('[data-panel]'));

    function show(value) {
      buttons.forEach(function (button) {
        button.setAttribute('aria-pressed', String(button.getAttribute(key) === value));
      });
      panels.forEach(function (panel) {
        if (panel.getAttribute('data-panel') === value) panel.removeAttribute('hidden');
        else panel.setAttribute('hidden', '');
      });
    }

    buttons.forEach(function (button) {
      button.addEventListener('click', function () {
        show(button.getAttribute(key));
      });
    });
  }

  function init() {
    readingPosition();
    quiz();
    timing();
    sortableTables();
    stackFocus();
    switchPanels('sig-steps', 'data-step');
    switchPanels('arch', 'data-comp');
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
