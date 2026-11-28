(function () {
  var A = window.Arcade, root = A.root;
  var WORDS = ['ALGORITHM','CALCULUS','THESIS','LECTURE','SEMESTER','LIBRARY','PHYSICS','CHEMISTRY','BIOLOGY','NETWORK','DATABASE','FUNCTION','VARIABLE','PROJECT','EXAMINATION','TUTORIAL','HOSTEL','CAMPUS','GRADUATE','SCHOLAR','ENGINEER','CIRCUIT','VOLTAGE','THERMAL','MATRIX','VECTOR','INTEGRAL','PROBABILITY','STATISTICS','ECONOMICS','HISTORY','GEOLOGY','SOFTWARE','COMPILER','PROTOCOL','SYLLABUS','ASSIGNMENT','REVISION','FLASHCARD','TIMETABLE','DEADLINE','RESEARCH','CITATION','DEGREE','CURRICULUM','PRACTICAL','LABORATORY','DIAGRAM','EQUATION','HYPOTHESIS'];
  function shuffle(a) { for (var i = a.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)); var t = a[i]; a[i] = a[j]; a[j] = t; } return a; }
  function scrambled(w) { var s; do { s = shuffle(w.split('')).join(''); } while (s === w); return s; }
  function start() {
    var words = shuffle(WORDS.slice()), idx = 0, score = 0, t = 90, hinted = false, timer;
    root.innerHTML = '<div class="text-center"><p class="text-sm text-slate-500">Time <span id="s-t" class="font-bold">90</span>s · Score <span id="s-s" class="font-bold">0</span></p>' +
      '<p id="s-w" class="font-display text-4xl tracking-widest font-bold my-6"></p><p id="s-h" class="text-sm text-slate-500 h-5"></p>' +
      '<input id="s-i" autocomplete="off" autocapitalize="characters" class="w-64 text-center text-xl uppercase rounded-xl border border-slate-300 dark:border-slate-600 dark:bg-slate-900 px-3 py-2" placeholder="Your answer">' +
      '<div class="mt-4 flex justify-center gap-2"><button id="s-hint" class="rounded-xl border border-slate-300 dark:border-slate-600 px-4 py-2 text-sm">Hint (-10)</button><button id="s-skip" class="rounded-xl border border-slate-300 dark:border-slate-600 px-4 py-2 text-sm">Skip</button></div></div>';
    var input = document.getElementById('s-i');
    function next() { hinted = false; document.getElementById('s-h').textContent = ''; document.getElementById('s-w').textContent = scrambled(words[idx % words.length]); input.value = ''; input.focus(); }
    input.addEventListener('keydown', function (e) {
      if (e.key !== 'Enter') return;
      if (input.value.trim().toUpperCase() === words[idx % words.length]) { score += hinted ? 15 : 25; idx++; document.getElementById('s-s').textContent = score; next(); }
      else { input.classList.add('border-rose-500'); setTimeout(function () { input.classList.remove('border-rose-500'); }, 300); }
    });
    document.getElementById('s-hint').onclick = function () { if (hinted) return; hinted = true; score = Math.max(0, score - 10); document.getElementById('s-s').textContent = score; document.getElementById('s-h').textContent = 'Starts with ' + words[idx % words.length][0] + ', ' + words[idx % words.length].length + ' letters'; };
    document.getElementById('s-skip').onclick = function () { idx++; next(); };
    timer = setInterval(function () { t--; document.getElementById('s-t').textContent = t; if (t <= 0) { clearInterval(timer); A.over('scramble', score, start); } }, 1000);
    next();
  }
  root.innerHTML = '<div class="text-center py-10"><button id="go" class="' + A.btn + '">Start (90 seconds)</button></div>';
  document.getElementById('go').onclick = start;
})();
