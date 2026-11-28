(function () {
  var A = window.Arcade, root = A.root;
  var LINES = [[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]];
  function winner(b) { for (var i = 0; i < LINES.length; i++) { var l = LINES[i]; if (b[l[0]] && b[l[0]] === b[l[1]] && b[l[0]] === b[l[2]]) return b[l[0]]; } return b.every(Boolean) ? 'draw' : null; }
  function minimax(b, turn) {
    var w = winner(b); if (w === 'O') return 1; if (w === 'X') return -1; if (w === 'draw') return 0;
    var best = turn === 'O' ? -2 : 2;
    for (var i = 0; i < 9; i++) if (!b[i]) { b[i] = turn; var v = minimax(b, turn === 'O' ? 'X' : 'O'); b[i] = null; best = turn === 'O' ? Math.max(best, v) : Math.min(best, v); }
    return best;
  }
  function cpu(b) {
    var free = []; for (var i = 0; i < 9; i++) if (!b[i]) free.push(i);
    if (Math.random() < 0.35) return free[Math.floor(Math.random() * free.length)];   // sometimes makes a mistake, so you can win
    var bestMove = free[0], bestVal = -2;
    free.forEach(function (m) { b[m] = 'O'; var v = minimax(b, 'X'); b[m] = null; if (v > bestVal) { bestVal = v; bestMove = m; } });
    return bestMove;
  }
  function start() {
    var round = 1, total = 0, wins = 0;
    function play() {
      var b = Array(9).fill(null), over = false;
      root.innerHTML = '<div class="text-center"><p class="text-sm text-slate-500">Round ' + round + '/5 · Score ' + total + ' · You are X</p><div id="t-b" class="grid grid-cols-3 gap-2 w-60 mx-auto my-5"></div><p id="t-m" class="h-6 text-sm font-semibold"></p></div>';
      var grid = document.getElementById('t-b');
      function render() { grid.innerHTML = ''; b.forEach(function (v, i) { var c = document.createElement('button'); c.className = 'h-20 rounded-xl border border-slate-300 dark:border-slate-600 text-3xl font-bold ' + (v === 'X' ? 'text-brand-600' : 'text-rose-500'); c.textContent = v || ''; c.onclick = function () { move(i); }; grid.appendChild(c); }); }
      function finish(w) {
        over = true; var pts = w === 'X' ? 100 : w === 'draw' ? 30 : 0; total += pts; if (w === 'X') wins++;
        document.getElementById('t-m').textContent = w === 'X' ? 'You win! +100' : w === 'draw' ? 'Draw +30' : 'Computer wins';
        setTimeout(function () { if (round >= 5) A.over('tictactoe', total, start); else { round++; play(); } }, 1100);
      }
      function move(i) {
        if (over || b[i]) return; b[i] = 'X'; var w = winner(b); render();
        if (w) return finish(w);
        b[cpu(b)] = 'O'; w = winner(b); render(); if (w) finish(w);
      }
      render();
    }
    play();
  }
  root.innerHTML = '<div class="text-center py-10"><button id="go" class="' + A.btn + '">Start best of five</button></div>';
  document.getElementById('go').onclick = start;
})();
