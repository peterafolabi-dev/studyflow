(function () {
  var A = window.Arcade, root = A.root;
  function start() {
    root.innerHTML = '<p class="text-center text-slate-500 py-10">Loading questions…</p>';
    fetch(root.dataset.quizUrl).then(function (r) { return r.json(); }).then(function (data) {
      var qs = data.questions, i = 0, score = 0, left = 15, timer, locked = false;
      function show() {
        locked = false; left = 15;
        var q = qs[i];
        root.innerHTML = '<p class="text-sm text-slate-500">Question ' + (i + 1) + '/' + qs.length + ' · <span id="q-t" class="font-bold">15</span>s · Score ' + score + '</p>' +
          '<p class="font-display text-xl font-bold my-4">' + A.esc(q.q) + '</p><div class="space-y-2" id="q-o"></div>';
        q.options.forEach(function (o, idx) {
          var b = document.createElement('button'); b.className = A.optBtn; b.textContent = o; b.onclick = function () { pick(idx, b); };
          document.getElementById('q-o').appendChild(b);
        });
        clearInterval(timer);
        timer = setInterval(function () { left--; var el = document.getElementById('q-t'); if (el) el.textContent = left; if (left <= 0) pick(-1); }, 1000);
      }
      function pick(idx, btn) {
        if (locked) return; locked = true; clearInterval(timer);
        var q = qs[i], buttons = document.querySelectorAll('#q-o button');
        if (idx === q.answer) { score += 100 + left * 2; if (btn) btn.classList.add('bg-emerald-100', 'border-emerald-500'); }
        else { if (btn) btn.classList.add('bg-rose-100', 'border-rose-500'); }
        if (buttons[q.answer]) buttons[q.answer].classList.add('bg-emerald-100', 'border-emerald-500');
        setTimeout(function () { i++; if (i >= qs.length) { A.over('quiz', Math.min(score, 1500), start); } else { show(); } }, 900);
      }
      show();
    });
  }
  start();
})();
