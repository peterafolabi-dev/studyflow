function normalizeMathDelimiters(text) {
    if (!text) return '';
    let res = text;

    // 1. \[ ... \] -> $$ ... $$
    res = res.replace(/\\\[([\s\S]*?)\\\]/g, (match, formula) => `\n$$\n${formula.trim()}\n$$\n`);

    // 2. \( ... \) -> $ ... $
    res = res.replace(/\\\(([\s\S]*?)\\\)/g, (match, formula) => `$${formula.trim()}$`);

    // 3. Handle plain [ formula ] on its own line where backslashes were stripped
    res = res.replace(/(?:^|\n)\s*\[\s*([^\]\n]+(?=[=+\-^*/\\_])[^\]\n]*)\s*\]\s*(?=\n|$)/gm, (match, formula) => {
        return `\n$$\n${formula.trim()}\n$$\n`;
    });

    // 4. Handle plain ( formula ) on its own line where backslashes were stripped
    res = res.replace(/(?:^|\n)\s*\(\s*([^)\n]+(?=[=+\-^*/\\_])[^)\n]*)\s*\)\s*(?=\n|$)/gm, (match, formula) => {
        return `\n$$\n${formula.trim()}\n$$\n`;
    });

    // 5. Handle inline parenthesized equations like (f(x)=x^3-4x^2+2x-5) or bracketed equations like [ f'(x)=... ]
    res = res.replace(/\(\s*([a-zA-Z]'?\([a-zA-Z]\)\s*=[^)\n]+)\s*\)/g, (match, formula) => `$${formula.trim()}$`);
    res = res.replace(/\[\s*([a-zA-Z]'?\([a-zA-Z]\)\s*=[^\]\n]+)\s*\]/g, (match, formula) => `$$${formula.trim()}$$`);

    return res;
}

const input1 = "Function: (f(x)=x^3-4x^2+2x-5) and derivative [ f'(x)=3x^2-8x+2 ]";
console.log("Input 1:");
console.log(normalizeMathDelimiters(input1));

const input2 = `**Card 1**
**Front:** What is the derivative of (f(x)=x^3-4x^2+2x-5)?
**Back:** The derivative is:
[ f'(x)=3x^2-8x+2 ]`;

console.log("\nInput 2:");
console.log(normalizeMathDelimiters(input2));
