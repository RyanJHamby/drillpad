trait Shape {
    fn area(&self) -> f64;
    fn name(&self) -> &str;
    fn describe(&self) -> String {
        format!("{} with area {:.2}", self.name(), self.area())
    }
}

struct Circle {
    radius: f64,
}

struct Rectangle {
    width: f64,
    height: f64,
}

struct Triangle {
    base: f64,
    height: f64,
}

impl Shape for Circle {
    fn area(&self) -> f64 {
        std::f64::consts::PI * self.radius * self.radius
    }
    fn name(&self) -> &str {
        "circle"
    }
}

impl Shape for Rectangle {
    fn area(&self) -> f64 {
        self.width * self.height
    }
    fn name(&self) -> &str {
        "rectangle"
    }
}

impl Shape for Triangle {
    fn area(&self) -> f64 {
        self.base * self.height / 2.0
    }
    fn name(&self) -> &str {
        "triangle"
    }
}

fn total_area(shapes: &[Box<dyn Shape>]) -> f64 {
    shapes.iter().map(|s| s.area()).sum()
}

fn largest<'a>(shapes: &'a [Box<dyn Shape>]) -> Option<&'a dyn Shape> {
    let mut best: Option<&'a dyn Shape> = None;
    for s in shapes {
        let s: &'a dyn Shape = s.as_ref();
        match best {
            Some(b) if s.area() <= b.area() => {}
            _ => best = Some(s),
        }
    }
    best
}

fn names_by_area(shapes: &[Box<dyn Shape>]) -> Vec<String> {
    let mut items: Vec<(f64, &str)> = shapes.iter().map(|s| (s.area(), s.name())).collect();
    items.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap());
    items.into_iter().map(|(_, n)| n.to_string()).collect()
}
