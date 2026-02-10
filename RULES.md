# Rat Scramble - Rules

## Overview
Rat Scramble is a 4-player political board game of shifting alliances and social coordination. Players negotiate, make binding deals, and vote on proposals to earn points based on their character's unique interests.

## Components
- 4 Character cards
- 20 Proposal cards
- 24 Effect cards (16 unique + 8 null)
- 4 Vote tokens (numbered 1-4)
- Promise tokens (20 total - 5 per player)
- Season buckets/bells tracker

## Characters & Interests

Each character has one season that gives **+2 points per bell**, one that gives **+1 point per bell**, and one that gives **-1 point per bell**.

| Character | +2 | +1 | -1 |
|-----------|-----|-----|------|
| Carmichael | Winter | Spring | Summer |
| Quincy | Autumn | Winter | Spring |
| Medici | Summer | Autumn | Winter |
| D'Ambrosio | Spring | Summer | Autumn |

## Setup

1. Each player selects a character and takes 5 promise tokens
2. Place the 4 vote tokens in the center of the table
3. Shuffle the proposal deck (20 cards) and effect deck (24 cards)

## Game Flow

The game lasts exactly **10 rounds**. Each round consists of:

### 1. Deal Phase
- Draw 2 proposal cards
- Draw 2 effect cards for each proposal (4 total)
  - First effect applies to the Majority outcome
  - Second effect applies to the Consensus outcome
- Place proposals face-up with their associated effect cards

### 2. Negotiation Phase
- Players discuss, negotiate, and make deals
- **All verbal agreements are binding** unless impossible to fulfill
- Players may take vote tokens to end their negotiation phase

#### Vote Tokens
- Vote token **3** must be taken first (any player can grab it)
- After token 3 is taken, tokens 4, 2, and 1 become available in any order
- Once a player takes a vote token, they cannot make **new** binding agreements in that round
- Existing binding agreements remain binding and may be enforced by the referee
- Players with vote tokens may still speak

### 3. Voting Phase
- Begins when all 4 players have taken vote tokens
- Players vote in order (1, 2, 3, 4)
- Players **cannot abstain**
- The proposal with majority votes (3 or 4 votes) passes
- In a tie (2-2), **neither proposal passes** - no bells awarded

#### Promise Token Voting Manipulation
- **During voting only**, after a player has voted, other players may use promise tokens to change that vote
- A player's vote can be changed **maximum 2 times per round**
- **Method 1**: Use a promise token from the target player that they previously gave you
- **Method 2**: Give the target player **3 of your own promise tokens** to force their vote change
- When a vote is changed, the player **is aware** their vote was changed
- Used promise tokens return to their original owner

### 4. Resolution Phase
- Determine if the winning proposal passed by Majority (3 votes) or Consensus (4 votes)
- Award bells to seasons as indicated by the proposal outcome
- Apply the effect card associated with the passing outcome
- Discard proposal and effect cards
- Return vote tokens to center
- **Reshuffle all effect cards** and draw 4 new ones for next round

## Proposal Cards

**Key:** S=Summer, P=Spring, A=Autumn, W=Winter

There are 5 categories of proposals:

Here's a key to understand them:
A = Same season
B = next season
C = season after next season ("opposite" season)
D = previous season (season after "opposite" season)

Max Proposal: AAA / AAAB
Spread Proposal: ABC / AAAD
Wild Proposal: AAA / BBDD
Rivalry Proposal: AAB / BBAA
Upset Proposal: ABB / ACCD

Each of the proposals listed below are in the same order, Max, Spread, Wild, Rivalry, Upset.

### Winter Proposals
| Proposal | Majority | Consensus |
|----------|----------|-----------|
| Winter Solstice | WWP | WWWW 
| Winter in Chorus | WPS | WWWA
| Winter All-Aglow | WWW | PPAA
| Winter in Harmony | WWP | PPWW
| Winter Awake | WPP | WSSA

### Spring Proposals
| Proposal | Majority | Consensus |
|----------|----------|-----------|
| Spring Equinox | PPS | PPPP |
| Spring In Bloom | PSA | PPPW |
| Spring In Quiet | PPP | SSWW |
| Spring Overflowing | PPS | SSPP |
| Spring-At-The-Door | PSS | PAAW |

### Autumn Proposals
| Proposal | Majority | Consensus |
|----------|----------|-----------|
| Autumn Equinox | AAW | AAAA |
| Autumn In Vain | AWP | AAAW |
| Autumn In Flight | AAA | WWPP |
| Autumn In Memory | AAW | WWAA |
| Autumn In Mourning | AWW | APPS |

### Summer Proposals
| Proposal | Majority | Consensus |
|----------|----------|-----------|
| Summer Solstice | SSA | SSSS |
| Summer Waking | SAW | SSSP |
| Summer Bursting | SSS | AAPP |
| Summer Singing | SSA | AASS |
| Summer in Glory | SAA | SWWP |

## Effect Cards

### Toggle Effects (Persistent)
These remain active until the same card is drawn and passed again, which disables it.

- **Clairvoyant**: Proposal deck is turned face-up and visible to all players
- **Shotgun**: Player with vote token 1 can break ties
- **Flea Market**: Players can trade other players' promise tokens between each other

### Event Effects (One-time)
These apply immediately when the associated outcome passes.

- **Highway Robbery**: Each player takes 1 promise token from another player (if available)
- **Jubilee**: All promise tokens return to their owners
- **Secret Santa**: Each player gives 1 promise token to another player of their choice
- **Gemini Season**: Promise tokens are doubled (each token can be used twice) *(disabled in current simulation build)*
- **Transformation**: Players may transform their promise tokens into tokens from different players (cannot create tokens from players with no tokens)

### Null Effects
8 cards that have no effect when passed.

## Promise Tokens

- Each player starts with **5 promise tokens**
- Tokens are given to other players as part of deals
- Tokens can only be used to change votes during the voting phase
- When a token is used, it returns to its original owner
- If a player runs out of tokens, they cannot give out more until tokens are returned to them
- **You cannot use your own promise tokens on yourself**

## Winning the Game

After all 10 rounds (when all 20 proposals have been voted on):

1. Count bells in each season bucket
2. Calculate each player's score based on their character's interests:
   - +2 points per bell in their +2 season
   - +1 point per bell in their +1 season
   - -1 point per bell in their -1 season
3. Players with **15+ points** win
4. Players with **<15 points** lose

**Note**: The threshold (default 15) can be adjusted for game length/preference. Multiple players can win or lose.

## Key Rules Summary

- Verbal agreements made before voting are binding unless impossible to fulfill
- Once you take a vote token, you cannot make new binding agreements
- Existing binding agreements remain enforceable by the referee
- Vote token 3 must be taken first
- Votes can be changed maximum 2 times per player per round
- Ties result in no bells awarded
- Effect cards reshuffle each round
- Game ends after 10 rounds (all proposals used)
