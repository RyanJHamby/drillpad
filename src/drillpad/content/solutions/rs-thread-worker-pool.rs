use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::{mpsc, Arc, Mutex};
use std::thread;

type Job = Box<dyn FnOnce() + Send + 'static>;

struct ThreadPool {
    workers: Vec<thread::JoinHandle<()>>,
    sender: Option<mpsc::Sender<Job>>,
}

impl ThreadPool {
    fn new(size: usize) -> ThreadPool {
        assert!(size >= 1, "pool needs at least one worker");
        let (tx, rx) = mpsc::channel::<Job>();
        let rx = Arc::new(Mutex::new(rx));
        let mut workers = Vec::with_capacity(size);
        for _ in 0..size {
            let rx = Arc::clone(&rx);
            workers.push(thread::spawn(move || loop {
                // The guard is a temporary: it is released before the job runs.
                let msg = rx.lock().unwrap().recv();
                match msg {
                    Ok(job) => {
                        let _ = catch_unwind(AssertUnwindSafe(job));
                    }
                    Err(_) => break,
                }
            }));
        }
        ThreadPool { workers, sender: Some(tx) }
    }

    fn size(&self) -> usize {
        self.workers.len()
    }

    fn execute<F>(&self, f: F)
    where
        F: FnOnce() + Send + 'static,
    {
        self.sender
            .as_ref()
            .expect("pool is shutting down")
            .send(Box::new(f))
            .expect("workers have exited");
    }

    fn submit<T, F>(&self, f: F) -> mpsc::Receiver<T>
    where
        F: FnOnce() -> T + Send + 'static,
        T: Send + 'static,
    {
        let (tx, rx) = mpsc::channel();
        self.execute(move || {
            let _ = tx.send(f());
        });
        rx
    }
}

impl Drop for ThreadPool {
    fn drop(&mut self) {
        drop(self.sender.take());
        for h in self.workers.drain(..) {
            let _ = h.join();
        }
    }
}
