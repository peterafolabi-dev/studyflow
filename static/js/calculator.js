/* StudyFlow calculator: a safe expression parser (no eval) plus a small keypad UI.
 *
 * Grammar (recursive descent):
 *   expr    := term (('+' | '-') term)*
 *   term    := unary (('*' | '/') unary | <implicit ×> unary)*
 *   unary   := ('+' | '-') unary | power
 *   power   := postfix ('^' unary)?          (right-associative)
 *   postfix := primary ('%' | '!')*
 *   primary := number | constant | func '(' expr ')' | '√' unary | '(' expr ')'
 */
(function (root) {
  'use strict';

  const FUNCS = {
    sin: (x, deg) => Math.sin(deg ? (x * Math.PI) / 180 : x),
    cos: (x, deg) => Math.cos(deg ? (x * Math.PI) / 180 : x),
    tan: (x, deg) => {
      if (deg && Math.abs(x % 180) === 90) return NaN; // tan(90°) is undefined
      return Math.tan(deg ? (x * Math.PI) / 180 : x);
    },
    asin: (x, deg) => (deg ? (Math.asin(x) * 180) / Math.PI : Math.asin(x)),
    acos: (x, deg) => (deg ? (Math.acos(x) * 180) / Math.PI : Math.acos(x)),
    atan: (x, deg) => (deg ? (Math.atan(x) * 180) / Math.PI : Math.atan(x)),
    sqrt: (x) => Math.sqrt(x),
    ln: (x) => Math.log(x),
    log: (x) => Math.log10(x),
    abs: (x) => Math.abs(x),
  };
  const CONSTANTS = { pi: Math.PI, 'π': Math.PI, e: Math.E };

  function tokenize(text) {
    const src = String(text)
      .replace(/×/g, '*').replace(/÷/g, '/').replace(/−/g, '-').replace(/\s+/g, '');
    const tokens = [];
    let i = 0;
    while (i < src.length) {
      const ch = src[i];
      if (/[0-9.]/.test(ch)) {
        let j = i;
        while (j < src.length && /[0-9.]/.test(src[j])) j++;
        const raw = src.slice(i, j);
        if ((raw.match(/\./g) || []).length > 1 || raw === '.') throw new Error('Bad number');
        tokens.push({ type: 'num', value: parseFloat(raw) });
        i = j;
      } else if (/[a-zA-Zπ]/.test(ch)) {
        let j = i;
        while (j < src.length && /[a-zA-Zπ]/.test(src[j])) j++;
        tokens.push({ type: 'name', value: src.slice(i, j).toLowerCase() });
        i = j;
      } else if ('+-*/^()%!√'.includes(ch)) {
        tokens.push({ type: 'op', value: ch });
        i++;
      } else {
        throw new Error(`Unexpected "${ch}"`);
      }
    }
    return tokens;
  }

  function factorial(n) {
    if (!Number.isInteger(n) || n < 0 || n > 170) return NaN;
    let r = 1;
    for (let k = 2; k <= n; k++) r *= k;
    return r;
  }

  function evaluate(text, options) {
    const deg = !options || options.degrees !== false;
    const ans = (options && Number.isFinite(options.ans)) ? options.ans : 0;
    const tokens = tokenize(text);
    if (!tokens.length) throw new Error('Empty');
    let pos = 0;
    const peek = () => tokens[pos];
    const isOp = (t, v) => t && t.type === 'op' && t.value === v;
    const expect = (v) => {
      if (!isOp(peek(), v)) throw new Error(`Expected "${v}"`);
      pos++;
    };
    // A token that can start a primary, used for implicit multiplication like 2π or 3(4).
    const startsPrimary = (t) => t && (t.type === 'num' || t.type === 'name' || isOp(t, '(') || isOp(t, '√'));

    function primary() {
      const t = peek();
      if (!t) throw new Error('Incomplete');
      if (t.type === 'num') { pos++; return t.value; }
      if (isOp(t, '(')) { pos++; const v = expr(); expect(')'); return v; }
      if (isOp(t, '√')) { pos++; return Math.sqrt(unary()); }
      if (t.type === 'name') {
        pos++;
        if (t.value === 'ans') return ans;
        if (t.value in CONSTANTS) return CONSTANTS[t.value];
        if (t.value in FUNCS) {
          expect('(');
          const v = expr();
          expect(')');
          return FUNCS[t.value](v, deg);
        }
        throw new Error(`Unknown "${t.value}"`);
      }
      throw new Error(`Unexpected "${t.value}"`);
    }
    function postfix() {
      let v = primary();
      for (;;) {
        if (isOp(peek(), '%')) { pos++; v /= 100; }
        else if (isOp(peek(), '!')) { pos++; v = factorial(v); }
        else return v;
      }
    }
    function power() {
      const base = postfix();
      if (isOp(peek(), '^')) { pos++; return Math.pow(base, unary()); }
      return base;
    }
    function unary() {
      if (isOp(peek(), '-')) { pos++; return -unary(); }
      if (isOp(peek(), '+')) { pos++; return unary(); }
      return power();
    }
    function term() {
      let v = unary();
      for (;;) {
        const t = peek();
        if (isOp(t, '*')) { pos++; v *= unary(); }
        else if (isOp(t, '/')) { pos++; v /= unary(); }
        else if (startsPrimary(t)) { v *= unary(); }
        else return v;
      }
    }
    function expr() {
      let v = term();
      for (;;) {
        if (isOp(peek(), '+')) { pos++; v += term(); }
        else if (isOp(peek(), '-')) { pos++; v -= term(); }
        else return v;
      }
    }
    const result = expr();
    if (pos < tokens.length) throw new Error(`Unexpected "${tokens[pos].value}"`);
    if (!Number.isFinite(result)) throw new Error('Math error');
    return result;
  }

  function format(n) {
    if (Object.is(n, -0) || Math.abs(n) < 1e-12) return '0';
    const abs = Math.abs(n);
    if (abs >= 1e12 || abs < 1e-6) return n.toExponential(6).replace(/\.?0+e/, 'e');
    return String(parseFloat(n.toPrecision(12)));
  }

  root.StudyFlowCalc = { evaluate, format };
  if (typeof module !== 'undefined' && module.exports) module.exports = root.StudyFlowCalc;

  // ---------------- UI ----------------
  if (typeof document === 'undefined') return;
  document.addEventListener('DOMContentLoaded', () => {
    const box = document.querySelector('[data-calculator]');
    if (!box) return;
    const input = box.querySelector('[data-calc-input]');
    const preview = box.querySelector('[data-calc-preview]');
    const angle = box.querySelector('[data-calc-angle]');
    const historyList = box.querySelector('[data-calc-history]');
    const HISTORY_KEY = 'studyflow-calc-history';
    let degrees = true;
    let ans = 0;
    let history = [];
    try { history = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]').slice(0, 5); } catch (e) { history = []; }

    function renderHistory() {
      historyList.textContent = '';
      history.forEach((item) => {
        const li = document.createElement('li');
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'w-full text-left truncate rounded px-2 py-1 hover:bg-slate-800';
        btn.textContent = `${item.expr} = ${item.result}`;
        btn.title = 'Use this result';
        btn.addEventListener('click', () => { insert(item.result); });
        li.appendChild(btn);
        historyList.appendChild(li);
      });
      historyList.parentElement.classList.toggle('hidden', !history.length);
    }

    function livePreview() {
      const text = input.value.trim();
      if (!text) { preview.textContent = ''; return; }
      try { preview.textContent = '= ' + format(evaluate(text, { degrees, ans })); }
      catch (e) { preview.textContent = ''; }
    }

    function insert(text) {
      const start = input.selectionStart ?? input.value.length;
      const end = input.selectionEnd ?? input.value.length;
      input.value = input.value.slice(0, start) + text + input.value.slice(end);
      const caret = start + text.length - (text.endsWith('()') ? 1 : 0);
      input.focus();
      input.setSelectionRange(caret, caret);
      livePreview();
    }

    function calculate() {
      const text = input.value.trim();
      if (!text) return;
      try {
        const result = format(evaluate(text, { degrees, ans }));
        ans = parseFloat(result);
        history = [{ expr: text, result }, ...history].slice(0, 5);
        try { localStorage.setItem(HISTORY_KEY, JSON.stringify(history)); } catch (e) { /* optional */ }
        input.value = result;
        preview.textContent = '';
        renderHistory();
      } catch (error) {
        preview.textContent = error.message === 'Math error' ? 'Math error' : 'Check the expression';
      }
      input.focus();
    }

    box.addEventListener('click', (event) => {
      const key = event.target.closest('[data-key]');
      if (!key) return;
      const value = key.dataset.key;
      if (value === '=') calculate();
      else if (value === 'AC') { input.value = ''; preview.textContent = ''; input.focus(); }
      else if (value === 'DEL') {
        const start = input.selectionStart ?? input.value.length;
        const end = input.selectionEnd ?? input.value.length;
        if (start !== end) input.value = input.value.slice(0, start) + input.value.slice(end);
        else if (start > 0) { input.value = input.value.slice(0, start - 1) + input.value.slice(start); input.setSelectionRange(start - 1, start - 1); }
        input.focus();
        livePreview();
      } else if (value === 'ANGLE') {
        degrees = !degrees;
        angle.textContent = degrees ? 'DEG' : 'RAD';
        livePreview();
      } else insert(value);
    });
    input.addEventListener('input', livePreview);
    input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') { event.preventDefault(); calculate(); }
      else if (event.key === 'Escape') { input.value = ''; preview.textContent = ''; }
    });
    renderHistory();
  });
})(typeof window !== 'undefined' ? window : globalThis);
