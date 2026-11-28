(function () {
  var A = window.Arcade, root = A.root, N = 20, CELL = 18;
  function start() {
    root.innerHTML = '<div class="text-center"><p class="text-sm text-slate-500 mb-2">Score <span id="n-s" class="font-bold">0</span> · arrow keys, WASD or swipe</p>' +
      '<canvas id="n-c" width="' + N * CELL + '" height="' + N * CELL + '" class="mx-auto rounded-xl border border-slate-300 dark:border-slate-600 bg-slate-50 dark:bg-slate-950 touch-none max-w-full"></canvas>' +
      '<div class="mt-3 grid grid-cols-3 gap-2 w-40 mx-auto sm:hidden"><span></span><button data-d="u" class="rounded-lg border py-2">▲</button><span></span><button data-d="l" class="rounded-lg border py-2">◀</button><button data-d="d" class="rounded-lg border py-2">▼</button><button data-d="r" class="rounded-lg border py-2">▶</button></div></div>';
    var ctx = document.getElementById('n-c').getContext('2d');
    var snake = [{ x: 10, y: 10 }, { x: 9, y: 10 }, { x: 8, y: 10 }], dir = { x: 1, y: 0 }, queued = dir, food, score = 0, speed = 130, loop, dead = false;
    function place() { do { food = { x: Math.floor(Math.random() * N), y: Math.floor(Math.random() * N) }; } while (snake.some(function (s) { return s.x === food.x && s.y === food.y; })); }
    function turn(d) { var m = { u: [0, -1], d: [0, 1], l: [-1, 0], r: [1, 0] }[d]; if (m[0] === -dir.x && m[1] === -dir.y) return; queued = { x: m[0], y: m[1] }; }
    function key(e) { var k = { ArrowUp: 'u', w: 'u', ArrowDown: 'd', s: 'd', ArrowLeft: 'l', a: 'l', ArrowRight: 'r', d: 'r' }[e.key]; if (k) { e.preventDefault(); turn(k); } }
    document.addEventListener('keydown', key);
    root.querySelectorAll('button[data-d]').forEach(function (b) { b.onclick = function () { turn(b.dataset.d); }; });
    var tx, ty, c = document.getElementById('n-c');
    c.addEventListener('touchstart', function (e) { tx = e.touches[0].clientX; ty = e.touches[0].clientY; }, { passive: true });
    c.addEventListener('touchend', function (e) { var dx = e.changedTouches[0].clientX - tx, dy = e.changedTouches[0].clientY - ty; if (Math.abs(dx) > Math.abs(dy)) turn(dx > 0 ? 'r' : 'l'); else turn(dy > 0 ? 'd' : 'u'); }, { passive: true });
    function draw() {
      ctx.clearRect(0, 0, N * CELL, N * CELL);
      ctx.fillStyle = '#f43f5e'; ctx.fillRect(food.x * CELL + 2, food.y * CELL + 2, CELL - 4, CELL - 4);
      snake.forEach(function (s, i) { ctx.fillStyle = i ? '#7c3aed' : '#4c1d95'; ctx.fillRect(s.x * CELL + 1, s.y * CELL + 1, CELL - 2, CELL - 2); });
    }
    function tick() {
      dir = queued; var h = { x: snake[0].x + dir.x, y: snake[0].y + dir.y };
      if (h.x < 0 || h.y < 0 || h.x >= N || h.y >= N || snake.some(function (s) { return s.x === h.x && s.y === h.y; })) return end();
      snake.unshift(h);
      if (h.x === food.x && h.y === food.y) { score += 10; document.getElementById('n-s').textContent = score; place(); speed = Math.max(60, speed - 3); clearInterval(loop); loop = setInterval(tick, speed); } else { snake.pop(); }
      draw();
    }
    function end() { if (dead) return; dead = true; clearInterval(loop); document.removeEventListener('keydown', key); A.over('snake', score, start); }
    place(); draw(); loop = setInterval(tick, speed);
  }
  root.innerHTML = '<div class="text-center py-10"><button id="go" class="' + A.btn + '">Start</button></div>';
  document.getElementById('go').onclick = start;
})();
