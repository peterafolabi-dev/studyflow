/* Shared helpers for Game Zone games. */
(function () {
  var root = document.getElementById('game-root');
  function csrf() {
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }
  function esc(t) { var d = document.createElement('div'); d.textContent = t; return d.innerHTML; }
  window.Arcade = {
    root: root,
    esc: esc,
    btn: 'rounded-xl bg-brand-600 hover:bg-brand-700 text-white font-semibold px-5 py-2.5 transition',
    optBtn: 'w-full text-left rounded-xl border border-slate-300 dark:border-slate-600 px-4 py-3 hover:border-brand-500 hover:bg-brand-50 dark:hover:bg-slate-800 transition',
    submit: function (game, score) {
      var box = document.getElementById('game-result');
      box.classList.remove('hidden');
      box.innerHTML = 'Saving your score…';
      return fetch(root.dataset.submitUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
        body: JSON.stringify({ game: game, score: score })
      }).then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
        .then(function (res) {
          if (!res.ok) { box.innerHTML = esc(res.d.error || 'Could not save this score.'); return; }
          var d = res.d, html = '<p class="font-semibold">Score ' + score + (d.new_best ? ' · 🎉 new personal best!' : ' · best ' + d.best) + '</p>';
          html += '<p class="mt-1">' + (d.xp ? '+' + d.xp + ' XP' : 'Daily game XP limit reached') + (d.daily_bonus ? ' · 🔥 daily challenge done, +' + d.daily_bonus + ' bonus XP' : '') + '</p>';
          (d.badges || []).forEach(function (b) { html += '<p class="mt-1">🏅 New badge: ' + esc(b.icon + ' ' + b.name) + '</p>'; });
          box.innerHTML = html;
        }).catch(function () { box.innerHTML = 'Could not save this score. Check your connection.'; });
    },
    over: function (game, score, again) {
      root.innerHTML = '<div class="text-center py-10"><p class="text-5xl">🏁</p><p class="font-display text-2xl font-bold mt-3">Score: ' + score +
        '</p><button id="again" class="mt-5 ' + this.btn + '">Play again</button></div>';
      document.getElementById('again').onclick = function () { document.getElementById('game-result').classList.add('hidden'); again(); };
      this.submit(game, score);
    }
  };
})();
