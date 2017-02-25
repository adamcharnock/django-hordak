.. _accounting_for_developers:

Double Entry Accounting for Developers
======================================

Hordak is inherently aimed at software developers as it provides core
functionality only. Friendly interfaces can certainly be built on top of it, but
if you are here there is a good change you are a developer.

If you are learning about accounting as developer you may feel – as I did – that
most of the material available doesn't quite relate to the developer/STEM mindset. I
therefore provide some resources here that may be of use.

Accounting in six bullet points (& three footnotes)
---------------------------------------------------

I found the core explanation of double entry accounting to be confusing. After some
time I distilled it down to the following:

 #. Each account has a 'type' (asset, liability, income, expense, equity).
 #. **Debits decrease** the value of an account. Always. [1]_
 #. **Credits increase** the value of an account. Always. [1]_
 #. The sign of any **asset** or **expense** account balance is **always flipped** upon display (i.e. multiply by -1) [2]_ [3]_.
 #. A transaction is comprised of 1 or more credits **and** 1 or more debits (i.e. money must come from somewhere and then go somewhere).
 #. The value of a transaction's debits and credits must be equal (money into transaction = money out of transaction).


.. [1] This is absolutely not what accountancy teaches. You'll quickly see that there is a lot of wrangling over what
        account types get increased/decreased with a debit/credit. I've simplified this on the backend as I strongly feel
        this is a presentational issue, and not a business logic issue.


.. [2] `Peter Selinger's tutorial`_ will give an indication of why this is (hint: see the signs in the accounting equation).
        However, a simple
        explanation is, *'accountants don't like negative numbers.'* A more nuanced interpretation
        is that a positive number indicates not a positive amount of money, but a positive amount of
        whatever the account is. So an expense of $1,000 is a positive amount of expense, even though it
        probably means your $1,000 less well off.


.. [3] An upshot of this sign flipping in 4 is that points 2 & 3 appear not be be obeyed from an external perspective.
        If you debit (decrease) an account, then flip its sign, it will look like you have actually increased the
        account balance. This is because we are treating the sign of asset & expense accounts as a presentational issue,
        rather than something to be dealt with in the core business logic.

In a little more detail
-----------------------

I found `Peter Selinger's tutorial`_ to be very enlightening and is less terse than the functional description above.
The first section is short and covers single entry accounting, and then shows how one can expand that to create double
entry accounting. I found this background useful.

.. _Peter Selinger's tutorial: http://www.mathstat.dal.ca/~selinger/accounting/tutorial.html


Examples
--------

You live in a shared house. Everyone pays their share into a communal bank account
every month.

Example 1: Saving money to pay a bill (no sign flipping)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You pay the electricity bill every three months. Therefore every month you take £100
from everyone's contributions and put it into Electricity Payable account (a liability
account) in the knowledge that you will pay the bill from this account when it eventually arrives:

These accounts are income & liability accounts, so neither balance needs to be flipped (flipping
only applies to asset & expense accounts). Therefore:

* Balances before:

  * *Housemate Contribution* (income): £500
  * *Electricity Payable* (liability): £0

* **Transaction**:

  * £100 from *Housemate Contribution* to *Electricity Payable*

* Balances after:

  * *Housemate Contribution* (income): £400
  * *Electricity Payable* (liability): £100

This should also make intuitive sense. Some of the housemate contributions will be used to pay the electricity
bill, therefore the former decreases and the latter increases.

Example 2: Saving money to pay a bill (with sign flipping)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

At the start of every month each housemate pays into the communal bank account. We
should therefore represent this somehow in our double entry system (something we ignored in
example 1).

We have an account called *Bank* which is an asset account (because this is money
we actually have). We also have a *Housemate Contribution* account which is an
income account.

Therefore, **to represent the fact that we have been paid money, we must create a transaction**.
However, money cannot be injected from outside our double entry system, so how do we deal with this?

Let's show how we represent a single housemate's payment:

* Balances before:

  * *Bank* (asset): £0
  * *Housemate Contribution* (income): £0

* **Transaction:**

  * £500 from *Bank* to *Housemate Contribution*

* Balances after:

  * *Bank* (asset): -£500 * -1 = **£500**
  * *Housemate Contribution*  (income): £500

Because the bank account is an asset account, we flip the sign of its balance.
**The result is that both accounts increase in value.**
