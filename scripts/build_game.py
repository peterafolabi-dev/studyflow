import os

break_room_html = '''{% extends 'base.html' %}
{% block title %}The Break Room · StudyFlow{% endblock %}
{% block content %}
<div class="mb-6 fade-in-up">
  <h1 class="font-display text-4xl font-bold tracking-tight text-slate-900 dark:text-white mb-2">The Break Room 🎮</h1>
  <p class="text-slate-500 dark:text-slate-400 mt-1">You've earned a 5-minute brain break. Play a quick game of 2048!</p>
</div>

<div class="flex flex-col md:flex-row gap-8 fade-in-up">
    
    <!-- Game Container -->
    <div class="bg-[#bbada0] p-4 rounded-3xl shadow-2xl w-full max-w-[400px] mx-auto md:mx-0">
        <div class="flex justify-between items-center mb-4">
            <div class="bg-[#8f7a66] text-white px-4 py-2 rounded-xl font-bold">
                SCORE <br><span id="score" class="text-2xl">0</span>
            </div>
            <button id="restart-btn" class="bg-[#8f7a66] hover:bg-[#9f8b77] text-white font-bold py-3 px-6 rounded-xl transition">
                New Game
            </button>
        </div>
        
        <!-- Grid -->
        <div class="relative bg-[#a39485] p-3 rounded-xl w-full aspect-square grid grid-cols-4 grid-rows-4 gap-3" id="grid-container">
            <!-- JS will populate tiles -->
        </div>
    </div>

    <!-- Leaderboard / Instructions -->
    <div class="flex-1 bg-white/60 dark:bg-slate-900/60 backdrop-blur-xl border border-white/50 dark:border-slate-700/50 rounded-3xl p-8">
        <h2 class="font-display text-2xl font-bold mb-4">How to play</h2>
        <p class="text-slate-600 dark:text-slate-300 mb-6">Use your <strong>Arrow Keys</strong> (or swipe on mobile) to move the tiles. Tiles with the same number merge into one when they touch. Add them up to reach <strong>2048!</strong></p>
        
        <h3 class="font-display text-xl font-bold mb-3 text-brand-600 dark:text-brand-400">Study Advice</h3>
        <p class="text-slate-600 dark:text-slate-300">Games like this are perfect for the 5-minute break in your Pomodoro cycle. They give your brain a quick hit of dopamine without sucking you into a doom-scroll on social media. Play a round, then get back to work!</p>
        
        <div class="mt-8 flex gap-3">
            <a href="{% url 'study_room' %}" class="inline-block bg-brand-600 hover:bg-brand-700 text-white font-medium px-6 py-3 rounded-xl shadow-lg transition">
                Back to Study Room
            </a>
            <a href="{% url 'dashboard' %}" class="inline-block bg-slate-200 dark:bg-slate-800 hover:bg-slate-300 dark:hover:bg-slate-700 text-slate-800 dark:text-white font-medium px-6 py-3 rounded-xl shadow-sm transition">
                Dashboard
            </a>
        </div>
    </div>
</div>

<style>
    .tile {
        display: flex;
        justify-content: center;
        align-items: center;
        font-size: 2rem;
        font-weight: bold;
        border-radius: 8px;
        background-color: #cdc1b4;
        color: #776e65;
        transition: transform 0.15s ease-in-out;
    }
    .tile-2 { background: #eee4da; }
    .tile-4 { background: #ede0c8; }
    .tile-8 { background: #f2b179; color: white; }
    .tile-16 { background: #f59563; color: white; }
    .tile-32 { background: #f67c5f; color: white; }
    .tile-64 { background: #f65e3b; color: white; }
    .tile-128 { background: #edcf72; color: white; font-size: 1.5rem; box-shadow: 0 0 10px rgba(243, 215, 116, 0.5); }
    .tile-256 { background: #edcc61; color: white; font-size: 1.5rem; box-shadow: 0 0 15px rgba(243, 215, 116, 0.6); }
    .tile-512 { background: #edc850; color: white; font-size: 1.5rem; box-shadow: 0 0 20px rgba(243, 215, 116, 0.7); }
    .tile-1024 { background: #edc53f; color: white; font-size: 1.2rem; box-shadow: 0 0 25px rgba(243, 215, 116, 0.8); }
    .tile-2048 { background: #edc22e; color: white; font-size: 1.2rem; box-shadow: 0 0 30px rgba(243, 215, 116, 0.9); }
</style>

<script>
    const gridContainer = document.getElementById('grid-container');
    const scoreDisplay = document.getElementById('score');
    let board = [];
    let score = 0;

    function initGame() {
        board = [...Array(4)].map(e => Array(4).fill(0));
        score = 0;
        scoreDisplay.textContent = score;
        addRandomTile();
        addRandomTile();
        drawBoard();
    }

    function addRandomTile() {
        let empty = [];
        for(let r=0; r<4; r++) {
            for(let c=0; c<4; c++) {
                if(board[r][c] === 0) empty.push({r, c});
            }
        }
        if(empty.length > 0) {
            let rand = empty[Math.floor(Math.random() * empty.length)];
            board[rand.r][rand.c] = Math.random() < 0.9 ? 2 : 4;
        }
    }

    function drawBoard() {
        gridContainer.innerHTML = '';
        for(let r=0; r<4; r++) {
            for(let c=0; c<4; c++) {
                let val = board[r][c];
                let tile = document.createElement('div');
                tile.className = `tile ${val > 0 ? 'tile-'+val : ''}`;
                tile.textContent = val > 0 ? val : '';
                gridContainer.appendChild(tile);
            }
        }
    }

    function slide(row) {
        let arr = row.filter(val => val);
        let missing = 4 - arr.length;
        let zeros = Array(missing).fill(0);
        return arr.concat(zeros);
    }

    function combine(row) {
        for(let i=0; i<3; i++) {
            if(row[i] !== 0 && row[i] === row[i+1]) {
                row[i] *= 2;
                score += row[i];
                scoreDisplay.textContent = score;
                row[i+1] = 0;
            }
        }
        return row;
    }

    function operate(row) {
        row = slide(row);
        row = combine(row);
        row = slide(row);
        return row;
    }

    function moveLeft() {
        let changed = false;
        for(let r=0; r<4; r++) {
            let oldRow = [...board[r]];
            board[r] = operate(board[r]);
            if(oldRow.join(',') !== board[r].join(',')) changed = true;
        }
        return changed;
    }

    function moveRight() {
        let changed = false;
        for(let r=0; r<4; r++) {
            let oldRow = [...board[r]];
            let row = [...board[r]].reverse();
            row = operate(row);
            board[r] = row.reverse();
            if(oldRow.join(',') !== board[r].join(',')) changed = true;
        }
        return changed;
    }

    function moveUp() {
        let changed = false;
        for(let c=0; c<4; c++) {
            let col = [board[0][c], board[1][c], board[2][c], board[3][c]];
            let oldCol = [...col];
            col = operate(col);
            for(let r=0; r<4; r++) board[r][c] = col[r];
            if(oldCol.join(',') !== col.join(',')) changed = true;
        }
        return changed;
    }

    function moveDown() {
        let changed = false;
        for(let c=0; c<4; c++) {
            let col = [board[0][c], board[1][c], board[2][c], board[3][c]].reverse();
            let oldCol = [board[0][c], board[1][c], board[2][c], board[3][c]];
            col = operate(col);
            col.reverse();
            for(let r=0; r<4; r++) board[r][c] = col[r];
            if(oldCol.join(',') !== col.join(',')) changed = true;
        }
        return changed;
    }

    document.addEventListener('keydown', e => {
        if(['ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(e.key)) {
            e.preventDefault(); // stop scrolling
        }
        let changed = false;
        if(e.key === 'ArrowLeft') changed = moveLeft();
        else if(e.key === 'ArrowRight') changed = moveRight();
        else if(e.key === 'ArrowUp') changed = moveUp();
        else if(e.key === 'ArrowDown') changed = moveDown();
        
        if(changed) {
            addRandomTile();
            drawBoard();
        }
    });

    document.getElementById('restart-btn').addEventListener('click', initGame);
    initGame();
</script>
{% endblock %}'''

with open('templates/planner/break_room.html', 'w', encoding='utf-8') as f:
    f.write(break_room_html)

# Add View
with open('planner/views.py', 'r', encoding='utf-8') as f:
    views = f.read()
if 'def break_room' not in views:
    views += '''\n@login_required\ndef break_room(request):\n    return render(request, 'planner/break_room.html')\n'''
    with open('planner/views.py', 'w', encoding='utf-8') as f:
        f.write(views)

# Add URL
with open('planner/urls.py', 'r', encoding='utf-8') as f:
    urls = f.read()
if "path('break-room/', views.break_room, name='break_room')," not in urls:
    urls = urls.replace('urlpatterns = [', "urlpatterns = [\n    path('break-room/', views.break_room, name='break_room'),")
    with open('planner/urls.py', 'w', encoding='utf-8') as f:
        f.write(urls)

# Add to Dashboard Quick Links
with open('planner/views.py', 'r', encoding='utf-8') as f:
    views = f.read()
if "('Break Room', '🎮', 'break_room')" not in views:
    views = views.replace("('Timetable', '🗓️', 'timetable'),", "('Timetable', '🗓️', 'timetable'),\n        ('Break Room', '🎮', 'break_room'),")
    with open('planner/views.py', 'w', encoding='utf-8') as f:
        f.write(views)

print('Built The Break Room!')
