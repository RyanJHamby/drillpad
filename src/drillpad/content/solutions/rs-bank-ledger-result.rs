use std::collections::HashMap;
use std::fmt;

#[derive(Debug, Clone, PartialEq)]
enum LedgerError {
    AccountExists(String),
    UnknownAccount(String),
    InvalidAmount,
    SameAccount,
    InsufficientFunds { needed: u64, available: u64 },
    Overflow,
}

impl fmt::Display for LedgerError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            LedgerError::AccountExists(id) => write!(f, "account already exists: {}", id),
            LedgerError::UnknownAccount(id) => write!(f, "unknown account: {}", id),
            LedgerError::InvalidAmount => write!(f, "amount must be positive"),
            LedgerError::SameAccount => write!(f, "cannot transfer to the same account"),
            LedgerError::InsufficientFunds { needed, available } => {
                write!(f, "insufficient funds: needed {}, available {}", needed, available)
            }
            LedgerError::Overflow => write!(f, "balance overflow"),
        }
    }
}

impl std::error::Error for LedgerError {}

struct Account {
    balance: u64,
    entries: Vec<Entry>,
}

struct Ledger {
    accounts: HashMap<String, Account>,
    processed: HashMap<String, Result<(), LedgerError>>,
}

impl Ledger {
    fn new() -> Self {
        Ledger { accounts: HashMap::new(), processed: HashMap::new() }
    }

    fn account(&self, id: &str) -> Result<&Account, LedgerError> {
        self.accounts
            .get(id)
            .ok_or_else(|| LedgerError::UnknownAccount(id.to_string()))
    }

    fn create_account(&mut self, id: &str) -> Result<(), LedgerError> {
        if self.accounts.contains_key(id) {
            return Err(LedgerError::AccountExists(id.to_string()));
        }
        self.accounts.insert(id.to_string(), Account { balance: 0, entries: Vec::new() });
        Ok(())
    }

    fn deposit(&mut self, id: &str, amount: u64) -> Result<u64, LedgerError> {
        if amount == 0 {
            return Err(LedgerError::InvalidAmount);
        }
        let current = self.account(id)?.balance;
        let delta = i64::try_from(amount).map_err(|_| LedgerError::Overflow)?;
        let new_balance = current.checked_add(amount).ok_or(LedgerError::Overflow)?;
        let acct = self.accounts.get_mut(id).unwrap();
        acct.balance = new_balance;
        acct.entries.push(Entry { delta, counterparty: None });
        Ok(new_balance)
    }

    fn apply_transfer(&mut self, src: &str, dst: &str, amount: u64) -> Result<(), LedgerError> {
        if amount == 0 {
            return Err(LedgerError::InvalidAmount);
        }
        if src == dst {
            return Err(LedgerError::SameAccount);
        }
        let available = self.account(src)?.balance;
        let dst_balance = self.account(dst)?.balance;
        if available < amount {
            return Err(LedgerError::InsufficientFunds { needed: amount, available });
        }
        let delta = i64::try_from(amount).map_err(|_| LedgerError::Overflow)?;
        let new_dst = dst_balance.checked_add(amount).ok_or(LedgerError::Overflow)?;
        // Everything validated: mutate both legs together.
        let s = self.accounts.get_mut(src).unwrap();
        s.balance = available - amount;
        s.entries.push(Entry { delta: -delta, counterparty: Some(dst.to_string()) });
        let d = self.accounts.get_mut(dst).unwrap();
        d.balance = new_dst;
        d.entries.push(Entry { delta, counterparty: Some(src.to_string()) });
        Ok(())
    }

    fn transfer(&mut self, src: &str, dst: &str, amount: u64, txn_id: Option<&str>) -> Result<(), LedgerError> {
        if let Some(id) = txn_id {
            if let Some(stored) = self.processed.get(id) {
                return stored.clone();
            }
        }
        let result = self.apply_transfer(src, dst, amount);
        if let Some(id) = txn_id {
            self.processed.insert(id.to_string(), result.clone());
        }
        result
    }

    fn balance(&self, id: &str) -> Result<u64, LedgerError> {
        Ok(self.account(id)?.balance)
    }

    fn history(&self, id: &str) -> Result<Vec<Entry>, LedgerError> {
        Ok(self.account(id)?.entries.clone())
    }

    fn total(&self) -> u64 {
        self.accounts.values().map(|a| a.balance).sum()
    }
}
