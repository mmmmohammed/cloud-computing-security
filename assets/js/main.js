/* Cloud Computing Security — Module 01
   Canvas topology, scroll reveals, fallacy flip cards, quiz scoring. */
(function () {
  "use strict";

  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ------------------------------------------------------- hero topology -- */
  function topology() {
    var canvas = document.getElementById("topology");
    if (!canvas || !canvas.getContext) return;
    var ctx = canvas.getContext("2d");
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var W = canvas.clientWidth || 640;
    var H = Math.round(W * 0.8125);

    function size() {
      W = canvas.clientWidth || 640;
      H = Math.round(W * 0.8125);
      canvas.width = W * dpr;
      canvas.height = H * dpr;
      canvas.style.height = H + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    size();

    var N = 22;
    var nodes = [];
    for (var i = 0; i < N; i++) {
      nodes.push({
        x: 40 + Math.random() * (W - 80),
        y: 40 + Math.random() * (H - 80),
        vx: (Math.random() - 0.5) * 0.22,
        vy: (Math.random() - 0.5) * 0.22,
        r: 2 + Math.random() * 2.4,
        phase: Math.random() * Math.PI * 2
      });
    }

    var packets = [];
    for (var p = 0; p < 7; p++) {
      packets.push({ a: Math.floor(Math.random() * N), b: Math.floor(Math.random() * N), t: Math.random(), speed: 0.004 + Math.random() * 0.006 });
    }

    var running = true;
    var io = null;
    if ("IntersectionObserver" in window) {
      io = new IntersectionObserver(function (entries) {
        running = entries[0].isIntersecting;
        if (running) requestAnimationFrame(frame);
      }, { threshold: 0.05 });
      io.observe(canvas);
    }

    var LINK = Math.min(W, H) * 0.32;

    function draw(time) {
      ctx.clearRect(0, 0, W, H);

      // links
      for (var i = 0; i < N; i++) {
        for (var j = i + 1; j < N; j++) {
          var a = nodes[i], b = nodes[j];
          var dx = a.x - b.x, dy = a.y - b.y;
          var d = Math.sqrt(dx * dx + dy * dy);
          if (d > LINK) continue;
          var alpha = (1 - d / LINK) * 0.32;
          var g = ctx.createLinearGradient(a.x, a.y, b.x, b.y);
          g.addColorStop(0, "rgba(34,211,238," + alpha.toFixed(3) + ")");
          g.addColorStop(1, "rgba(139,92,246," + alpha.toFixed(3) + ")");
          ctx.strokeStyle = g;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
      }

      // packets travelling along links
      packets.forEach(function (pk) {
        var a = nodes[pk.a], b = nodes[pk.b];
        var x = a.x + (b.x - a.x) * pk.t;
        var y = a.y + (b.y - a.y) * pk.t;
        ctx.beginPath();
        ctx.arc(x, y, 2, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(34,211,238,0.95)";
        ctx.shadowColor = "rgba(34,211,238,0.9)";
        ctx.shadowBlur = 10;
        ctx.fill();
        ctx.shadowBlur = 0;
      });

      // nodes
      var t = time * 0.001;
      for (var k = 0; k < N; k++) {
        var n = nodes[k];
        var pulse = 0.55 + 0.45 * Math.sin(t * 1.6 + n.phase);
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r + pulse * 1.2, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(232,238,251," + (0.55 + pulse * 0.35).toFixed(2) + ")";
        ctx.fill();
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r + 5 + pulse * 5, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(34,211,238,0.07)";
        ctx.fill();
      }
    }

    function step() {
      nodes.forEach(function (n) {
        n.x += n.vx;
        n.y += n.vy;
        if (n.x < 24 || n.x > W - 24) n.vx *= -1;
        if (n.y < 24 || n.y > H - 24) n.vy *= -1;
      });
      packets.forEach(function (pk) {
        pk.t += pk.speed;
        if (pk.t >= 1) {
          pk.t = 0;
          pk.a = pk.b;
          pk.b = Math.floor(Math.random() * N);
        }
      });
    }

    function frame(time) {
      if (!running) return;
      step();
      draw(time);
      requestAnimationFrame(frame);
    }

    if (reduce) {
      draw(0); // static diagram, no motion
    } else {
      requestAnimationFrame(frame);
    }

    var rt = null;
    window.addEventListener("resize", function () {
      clearTimeout(rt);
      rt = setTimeout(size, 180);
    });
  }

  /* ------------------------------------------------------------ reveals -- */
  function reveals() {
    var items = document.querySelectorAll(".reveal");
    if (!("IntersectionObserver" in window) || reduce) {
      items.forEach(function (el) { el.classList.add("in"); });
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        var el = entry.target;
        var sibs = Array.prototype.slice.call(el.parentNode.children).filter(function (c) {
          return c.classList && c.classList.contains("reveal");
        });
        var i = Math.max(0, sibs.indexOf(el));
        el.style.transitionDelay = Math.min(i * 70, 420) + "ms";
        el.classList.add("in");
        io.unobserve(el);
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.12 });
    items.forEach(function (el) { io.observe(el); });
  }

  /* --------------------------------------------------------- flip cards -- */
  function flips() {
    document.querySelectorAll(".fallacy").forEach(function (card) {
      card.addEventListener("click", function () {
        var on = card.classList.toggle("is-flipped");
        card.setAttribute("aria-pressed", on ? "true" : "false");
      });
      card.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && card.classList.contains("is-flipped")) {
          card.classList.remove("is-flipped");
          card.setAttribute("aria-pressed", "false");
        }
      });
    });
  }

  /* --------------------------------------------------------------- quiz -- */
  function quiz() {
    var list = document.getElementById("quiz-list");
    if (!list) return;
    var total = list.querySelectorAll(".q").length;
    var answered = 0;
    var scoreText = document.getElementById("score-text");
    var scoreFill = document.getElementById("score-fill");

    list.querySelectorAll(".q").forEach(function (q) {
      var answer = q.dataset.answer;
      var opts = q.querySelectorAll(".opt");
      var why = q.querySelector(".why");

      opts.forEach(function (btn) {
        btn.addEventListener("click", function () {
          if (q.classList.contains("solved")) return;
          var picked = btn.dataset.opt;
          opts.forEach(function (o) {
            o.disabled = true;
            if (o.dataset.opt === answer) o.classList.add("correct");
          });
          if (picked !== answer) btn.classList.add("wrong");
          q.classList.add("solved");
          if (why) why.classList.add("show");
          answered++;
          if (scoreText) {
            scoreText.textContent = answered + " / " + total + " answered" + (answered === total ? " · done" : "");
          }
          if (scoreFill) scoreFill.style.width = (answered / total) * 100 + "%";
        });
      });
    });
  }

  /* ------------------------------------------------------------ counters -- */
  function counters() {
    var els = document.querySelectorAll("[data-count]");
    if (!els.length) return;

    function run(el) {
      var target = parseFloat(el.dataset.count || "0");
      var dec = parseInt(el.dataset.decimals || "0", 10);
      var unit = el.querySelector("small");
      var suffix = unit ? unit.outerHTML : "";
      var start = null;
      var dur = 1400;

      if (reduce) {
        el.innerHTML = target.toFixed(dec) + suffix;
        return;
      }
      function tick(ts) {
        if (start === null) start = ts;
        var p = Math.min((ts - start) / dur, 1);
        var eased = 1 - Math.pow(1 - p, 3);
        el.innerHTML = (target * eased).toFixed(dec) + suffix;
        if (p < 1) requestAnimationFrame(tick);
      }
      requestAnimationFrame(tick);
    }

    if (!("IntersectionObserver" in window)) {
      els.forEach(run);
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { run(e.target); io.unobserve(e.target); }
      });
    }, { threshold: 0.4 });
    els.forEach(function (el) { io.observe(el); });
  }

  function init() {
    topology();
    reveals();
    flips();
    quiz();
    counters();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
