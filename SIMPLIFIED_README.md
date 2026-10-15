# The Assignment, in Simple Words

This is a plain-language summary of the take-home assignment.
The official instructions are in [docs/ASSIGNMENT.md](docs/ASSIGNMENT.md). If the
two ever disagree, follow `docs/ASSIGNMENT.md`.

## The big idea

Three companies — **PrismHR**, **isolved**, and **UKG Ready** — sell payroll
software. All three store the same kind of information (employees, paychecks,
bank accounts, and so on), but each one stores it **differently**.

For example, an employee's first name is called:

- PrismHR: `firstName`
- isolved: `firstName`
- UKG Ready: `first_name`

And it gets harder than names. A status like "active employee" can be written
as a different code in each system, and some codes are not explained anywhere.

**Your job is to build a translator.** It takes data from any of the three
systems and turns it into **one standard format that you design**. After
translation, an employee looks the same no matter which system they came from.

## What data you need to translate

1. **Company:** the employer.
2. **Employee:** name, address, job, start date, salary, and so on. Include
   all the employee fields each system offers, not just a few.
3. **Direct deposit:** which bank account the paycheck goes to, and how much
   goes to each account.
4. **Deductions:** money taken out of a paycheck, like 401k or health
   insurance.
5. **Payroll:** each paycheck: hours worked, pay before and after taxes,
   and taxes withheld.

Keep the links between them, so you can tell which employees belong to which
company and which paychecks belong to which employee.

## What this repo gives you

- **API documentation** for each system, in the [`contracts/`](contracts/)
  folder. This is how you find out what each system's data looks like. The
  files are very large, so read only the parts you need.
  - PrismHR: an OpenAPI file.
  - isolved: two Swagger files. Use the **primary** one only and don't mix it
    with the alternate.
  - UKG Ready: saved HTML documentation pages plus extracted JSON schemas.
    There is no proper OpenAPI file.
- **Code lists** (`lookup-reference.json` in each provider folder). These
  explain some codes, but not all of them.
- **A tiny Python starter** in [`src/`](src/). It is basically empty, and you
  can ignore it. You can use any language.

There is **no ready-made sample data**. You create your own fake test data.

## The steps

1. **Read the docs** to find the employee, payroll, and other data in each
   system.
2. **Design your standard format.** Decide what a "standard employee" looks
   like.
3. **Make fake test data** shaped like each system's real responses.
4. **Write the translator code**, so each system's data becomes your standard
   format.
5. **Write tests** to show the translation is correct. They must run on your
   own computer without internet or passwords.
6. **Write down your decisions.** Whenever something is unclear, such as a
   code with no explanation or a missing field, note what you decided and why.

## Two extra things (both optional)

- **Live demo data:** if the organizer gives you an API key, you can look at
  real demo data from all three systems to check your understanding.
  See the "Access live demo data" section of [docs/ASSIGNMENT.md](docs/ASSIGNMENT.md).
  Never commit tokens or downloaded data.
- **Bonus:** translate in the reverse direction too, taking your standard
  employee and creating it inside one of the systems (for example, UKG Ready
  or PrismHR). A "dry run" that only shows the mapping is fine.

## What you hand in

A link to your own repository with:

- your code,
- a README explaining your approach and how to set it up and run it,
- a separate document explaining your assumptions and decisions, and why
  you made them.

## The most important point

They care most about **careful thinking**:

- Don't guess what a code means.
- Don't assume what unit a number is in. For example, some UKG time fields
  are in **milliseconds**, not hours.
- When data is missing, confusing, or different from what you expected,
  write it down along with what you decided.

Doing a smaller part very well is better than doing everything badly.

## Small traps in the starter code

- The starter only lists three data types (`company`, `employee`, `payroll`).
  The assignment asks for direct deposits and deductions too. Follow the assignment.
- Some starter tests expect the code to be unfinished, so they will fail once
  you build things. Replace or remove them.
