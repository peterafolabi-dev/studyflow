(function () {
  var A = window.Arcade, root = A.root;
  function start() {
    var score = 0, streak = 0, t = 60, answer = 0, timer;
    root.innerHTML = '<div class="text-center"><p class="text-sm text-slate-500">Time <span id="m-t" class="font-bold">60</span>s · Score <span id="m-s" class="font-bold">0</span> · Streak <span id="m-k" class="font-bold">0</span></p>' +
      '<p id="m-q" class="font-display text-5xl font-bold my-8"></p>' +
      '<input id="m-i" inputmode="numeric" autocomplete="off" class="w-40 text-center text-2xl rounded-xl border border-slate-300 dark:border-slate-600 dark:bg-slate-900 px-3 py-2" placeholder="?">' +
      '<p class="mt-3 text-xs text-slate-500">Type the answer and press Enter</p></div>';
    var input = document.getElementById('m-i');
    function next() {
      var level = Math.min(4, 1 + Math.floor(score / 80));
      var ops = ['+', '-', '×'], op = ops[Math.floor(Math.random() * (level > 1 ? 3 : 2))];
      var max = 8 + level * 8, a = 1 + Math.floor(Math.random() * max), b = 1 + Math.floor(Math.random() * max);
      if (op === '×') { a = 2 + Math.floor(Math.random() * (level + 8)); b = 2 + Math.floor(Math.random() * (level + 8)); }
      if (op === '-' && b > a) { var x = a; a = b; b = x; }
      answer = op === '+' ? a + b : op === '-' ? a - b : a * b;
      document.getElementById('m-q').textContent = a + ' ' + op + ' ' + b;
      input.value = ''; input.focus();
    }
    input.addEventListener('keydown', function (e) {
      if (e.key !== 'Enter' || input.value.trim() === '') return;
      if (parseInt(input.value, 10) === answer) { streak++; score += 10 + (streak % 5 === 0 ? 10 : 0); } else { streak = 0; score = Math.max(0, score - 5); }
      document.getElementById('m-s').textContent = score; document.getElementById('m-k').textContent = streak; next();
    });
    timer = setInterval(function () {
      t--; document.getElementById('m-t').textContent = t;
      if (t <= 0) { clearInterval(timer); A.over('math', score, start); }
    }, 1000);
    next();
  }
  root.innerHTML = '<div class="text-center py-10"><button id="go" class="' + A.btn + '">Start 60-second sprint</button></div>';
  document.getElementById('go').onclick = start;
})();
