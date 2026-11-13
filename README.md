# Do Japan's megabanks mean-revert?

Do MUFG (8306.T), SMFG (8316.T) and Mizuho (8411.T) bounce back after sharp
drops enough to beat buy-and-hold after trading costs? The rule was fixed in
advance in [PREREGISTRATION.md](PREREGISTRATION.md) (originally written for
Singapore banks; see Amendment 1 for the switch to Japan).

## Setup (Mac)

```bash
cd japan-megabanks-mean-reversion
python3 -m venv .venv          # a private Python just for this project
source .venv/bin/activate      # use it in this terminal (run again in each new terminal)
pip install -r requirements.txt
pytest                         # should run with no errors
```

_The rest of this README is filled in as the project grows._
