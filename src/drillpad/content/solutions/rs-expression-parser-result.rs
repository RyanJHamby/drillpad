fn tokenize(input: &str) -> Result<Vec<Token>, ParseError> {
    let mut out = Vec::new();
    let mut chars = input.chars().peekable();
    while let Some(&c) = chars.peek() {
        match c {
            c if c.is_whitespace() => {
                chars.next();
            }
            '+' => {
                out.push(Token::Plus);
                chars.next();
            }
            '-' => {
                out.push(Token::Minus);
                chars.next();
            }
            '*' => {
                out.push(Token::Star);
                chars.next();
            }
            '/' => {
                out.push(Token::Slash);
                chars.next();
            }
            '(' => {
                out.push(Token::LParen);
                chars.next();
            }
            ')' => {
                out.push(Token::RParen);
                chars.next();
            }
            c if c.is_ascii_digit() || c == '.' => {
                let mut text = String::new();
                while let Some(&d) = chars.peek() {
                    if d.is_ascii_digit() || d == '.' {
                        text.push(d);
                        chars.next();
                    } else {
                        break;
                    }
                }
                let n: f64 = text.parse().map_err(|_| ParseError::InvalidNumber(text.clone()))?;
                out.push(Token::Num(n));
            }
            other => return Err(ParseError::UnexpectedChar(other)),
        }
    }
    Ok(out)
}

struct Parser {
    tokens: Vec<Token>,
    pos: usize,
}

impl Parser {
    fn peek(&self) -> Option<Token> {
        self.tokens.get(self.pos).copied()
    }

    fn bump(&mut self) -> Option<Token> {
        let t = self.peek();
        if t.is_some() {
            self.pos += 1;
        }
        t
    }

    fn expr(&mut self) -> Result<f64, ParseError> {
        let mut acc = self.term()?;
        loop {
            match self.peek() {
                Some(Token::Plus) => {
                    self.pos += 1;
                    acc += self.term()?;
                }
                Some(Token::Minus) => {
                    self.pos += 1;
                    acc -= self.term()?;
                }
                _ => return Ok(acc),
            }
        }
    }

    fn term(&mut self) -> Result<f64, ParseError> {
        let mut acc = self.unary()?;
        loop {
            match self.peek() {
                Some(Token::Star) => {
                    self.pos += 1;
                    acc *= self.unary()?;
                }
                Some(Token::Slash) => {
                    self.pos += 1;
                    let d = self.unary()?;
                    if d == 0.0 {
                        return Err(ParseError::DivisionByZero);
                    }
                    acc /= d;
                }
                _ => return Ok(acc),
            }
        }
    }

    fn unary(&mut self) -> Result<f64, ParseError> {
        if self.peek() == Some(Token::Minus) {
            self.pos += 1;
            return Ok(-self.unary()?);
        }
        self.primary()
    }

    fn primary(&mut self) -> Result<f64, ParseError> {
        match self.bump() {
            None => Err(ParseError::UnexpectedEnd),
            Some(Token::Num(n)) => Ok(n),
            Some(Token::LParen) => {
                let v = self.expr()?;
                match self.bump() {
                    Some(Token::RParen) => Ok(v),
                    None => Err(ParseError::UnmatchedParen),
                    Some(t) => Err(ParseError::UnexpectedToken(t)),
                }
            }
            Some(t) => Err(ParseError::UnexpectedToken(t)),
        }
    }
}

fn evaluate(input: &str) -> Result<f64, ParseError> {
    let tokens = tokenize(input)?;
    let mut p = Parser { tokens, pos: 0 };
    let v = p.expr()?;
    match p.peek() {
        None => Ok(v),
        Some(Token::RParen) => Err(ParseError::UnmatchedParen),
        Some(t) => Err(ParseError::UnexpectedToken(t)),
    }
}
