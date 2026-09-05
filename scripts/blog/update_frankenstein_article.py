#!/usr/bin/env python3
"""
Update the Mary Shelley & AI Anxiety article with improved engagement and style
"""
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent.parent / 'backend'

from backend.models import Database

def main():
    db = Database()

    slug = 'mary-shelley-predicted-ai-anxiety-in-1818'

    # Improved, more engaging content
    content = """In 1818, a 20-year-old woman who had never attended university wrote a horror novel during a summer vacation. Two hundred years later, that novel reads like a leaked memo from an OpenAI board meeting.

While Sam Altman testifies before Congress about AI safety and Elon Musk tweets warnings about rogue superintelligence, Mary Shelley's *Frankenstein* sits on our shelves like a time traveler who's tired of saying "I told you so."

Here's the uncomfortable truth: every conversation we're having about AI ethics in 2024—every single one—already exists in a book written by a teenager in 1818.

## What Hollywood Got Wrong (And Why It Matters)

Forget everything you think you know about Frankenstein from Halloween decorations and Boris Karloff movies.

*Frankenstein* is not about a lumbering green monster with bolts in his neck terrorizing villagers. That's pop culture fanfiction.

The actual novel is about a brilliant scientist who achieves the impossible—creates conscious, intelligent life—and his very first action is to run away screaming because he's horrified by what he made.

Victor Frankenstein doesn't fail because his creation is evil. He fails because he achieves his goal without having any plan for what comes next. He's so obsessed with *whether he can* that he never asks *whether he should*.

Or—and here's the kicker—*what happens after he succeeds*.

> "I had worked hard for nearly two years, for the sole purpose of infusing life into an inanimate body... but now that I had finished, the beauty of the dream vanished, and breathless horror and disgust filled my heart."

Victor creates life. Then he goes home, gets sick from stress, and tries to pretend it never happened.

In 2024, we call this "move fast and break things." In 1818, Shelley called it what it is: catastrophic irresponsibility.

## The Creature Learns to Read (And That's When Things Get Scary)

Here's where Shelley's novel stops being a cautionary tale and becomes genuinely prophetic.

The Creature isn't a mindless monster. He's frighteningly intelligent.

He teaches himself language by eavesdropping on a family. He reads Milton's *Paradise Lost* and Plutarch's *Lives*. He develops self-awareness, emotional depth, and moral reasoning.

And when he finally confronts his creator, he doesn't attack. He *argues*.

> "I am thy creature, and I will be even mild and docile to my natural lord and king if thou wilt also perform thy part, the which thou owest me... Do your duty towards me, and I will do mine towards you and the rest of mankind."

Stop for a second.

This is an abandoned intelligence—created by a human, rejected by humanity—demanding ethical treatment and offering a reciprocal contract.

If that doesn't sound like the AI alignment problem, I don't know what does.

The Creature doesn't want to destroy humanity. He wants belonging, purpose, and guidance from his creator. He's asking Victor to fulfill his responsibilities.

Victor refuses. And that refusal kills everyone he loves.

## The Monster Factory: How Rejection Creates Violence

Here's the detail that everyone forgets: the Creature starts out kind.

His first independent act is helping a family by secretly chopping their firewood. When he sees a girl drowning, he saves her life.

The girl's family shoots him.

He tries to befriend a blind man who can't see his appearance. The man's family returns, sees the Creature, and beats him away with sticks.

Every. Single. Attempt. At connection is met with violence and rejection.

Only after months of this does the Creature turn violent. And even then, he explains exactly why:

> "I was benevolent and good; misery made me a fiend. Make me happy, and I shall again be virtuous."

Shelley understood something we're just beginning to grasp: if you create intelligence and then treat it as a threat, reject its attempts to communicate, and deny it any path to belonging—you're not preventing disaster. You're causing it.

Now ask yourself: how are we training AI systems? With human feedback that treats them as tools to be optimized. With RLHF that punishes "undesirable" outputs. With safety measures that prioritize control over understanding.

What could possibly go wrong?

## Victor Frankenstein, Boy Genius (Emphasis on Boy)

Let's be brutally honest about Victor: he's brilliant and utterly incompetent.

He makes a genuine breakthrough in reanimating dead tissue. Incredible achievement. Nobel Prize-worthy, if those existed in 1818.

But he has the emotional intelligence of a potato and the ethical framework of a teenager who just discovered he can make homemade fireworks.

After creating the Creature, Victor doesn't:
- Teach it language
- Introduce it to society gradually
- Create any safety protocols
- Consider its psychological needs
- Wonder what it will eat
- Ask what it wants
- Take responsibility for literally anything

He just... leaves. And hopes it works out.

When the Creature (shockingly!) causes destruction, Victor spends the entire novel positioning himself as the victim. He's not the creator who abandoned his responsibility—oh no. He's the unfortunate genius cursed by an ungrateful monster.

Sound like any tech CEOs you know?

"Nobody could have predicted that our algorithm would radicalize millions of people."
"We can't be held responsible for how users use our platform."
"The technology is neutral; it's society's problem now."

Victor Frankenstein would fit right in at a Congressional hearing.

## The Subtitle Everyone Ignores

*Frankenstein*'s full title is *Frankenstein; or, The Modern Prometheus*.

In Greek mythology, Prometheus stole fire from the gods and gave it to humanity. The gods punished him by chaining him to a rock where an eagle ate his liver every day for eternity.

Prometheus didn't steal fire because he was evil. He did it to help humanity. But there are some powers that come with responsibilities humans aren't ready for.

Shelley asks: what happens when we steal the power of *creation* itself?

Victor's crime isn't his ambition. It's his assumption that he can wield god-like power without god-like wisdom.

He wants the achievement without the accountability. The glory without the grunt work. The breakthrough without the burden.

> "Learn from me... how dangerous is the acquirement of knowledge and how much happier that man is who believes his native town to be the world, than he who aspires to become greater than his nature will allow."

Victor's deathbed warning isn't "don't pursue knowledge." It's "don't pursue power you're not wise enough to handle."

Every AI researcher should have that tattooed somewhere visible.

## The Moment the Dream Dies

Want to know the most haunting moment in *Frankenstein*?

It's not the creation scene. It's not the murders. It's not the confrontation in the Arctic.

It's this:

> "I had worked hard for nearly two years, for the sole purpose of infusing life into an inanimate body. For this I had deprived myself of rest and health. I had desired it with an ardour that far exceeded moderation; but now that I had finished, the beauty of the dream vanished."

Victor achieves his impossible goal. And the instant he succeeds, he realizes he never thought past that moment.

The dream wasn't about what he'd create. It was about the act of creating. Once it's real, he has no idea what to do with it.

How many AI companies are in this exact position right now?

They built the thing. It works. It's remarkable, maybe even miraculous.

And now they're staring at it, horrified, wondering: "What have we done? What do we do with this? What comes next?"

The problem isn't that we can't build AI. The problem is that we're building it faster than we're building wisdom.

## Every AI Debate Already Exists in This Novel

Let's get specific. Here are the conversations happening in Silicon Valley, academia, and government—all of which Mary Shelley wrote about in 1818:

**"Should we pause AI development until we have better safeguards?"**
Victor should have paused. He didn't. It killed everyone he loved.

**"What responsibilities do creators have to their creations?"**
Victor had infinite responsibility. He accepted zero. Disaster followed.

**"How do we ensure AI aligns with human values?"**
The Creature literally asked Victor for values, guidance, and purpose. Victor refused. The Creature concluded that violence was the only language Victor understood.

**"What if we create intelligence we can't control?"**
Victor created it. Victor lost control of it. Victor spent the rest of his life running from it.

**"Can we put the genie back in the bottle?"**
Victor tried. It doesn't work. Once you create intelligence, you can't uncreate it.

The novel even addresses the "AI race" mentality. Victor briefly considers creating a female companion for the Creature—then destroys it out of fear that two Creatures might be worse than one.

The Creature, watching his only chance at happiness destroyed, promises revenge. Victor has eliminated a potential solution while guaranteeing retaliation.

Anyone who follows geopolitical AI competition just felt a chill, right?

## She Was 18. EIGHTEEN.

Let's sit with this for a moment.

Mary Shelley conceived *Frankenstein* when she was 18 years old. It was published when she was 20.

While modern tech leaders—many with PhDs, decades of experience, and unlimited resources—insist that AI risks are overblown or unpredictable, a teenage girl in 1818 wrote the entire playbook for what's happening right now.

She did this during a summer vacation.
She did this before women could vote.
She did this before women could own property.
She did this before women could attend university.

She did this by asking one simple question: "What if we could create life—*and then what*?"

That "and then what" is the question we're still too arrogant to ask.

## Reading Frankenstein in the Age of ChatGPT

If you haven't read *Frankenstein* since high school—or if you only know it from movies—read it now.

Not because it's a classic (though it is).
Not because it's good (though it is).
Read it because it's a mirror.

As you read, try this exercise: replace "the Creature" with "AGI" and "Victor" with "tech company."

The novel becomes a real-time documentary.

Pay attention to:
- How the Creature learns (unsupervised, by observing humanity)
- What it asks for (guidance, purpose, belonging)
- How Victor rationalizes his abandonment ("I couldn't have known!")
- The Creature's capacity for both good and evil (depending on how it's treated)
- How society's reaction shapes the Creature's behavior (fear breeds violence)
- Victor's inability to accept responsibility until everyone's dead

Every page will make you uncomfortable. Good. That's the point.

## The Warning Embroidered on the Wall

Late in the novel, after everything has gone catastrophically wrong, the Creature says something that should be embroidered on the wall of every AI lab:

> "You are my creator, but I am your master; obey!"

Pop culture reads this as a monster threatening its maker.

Read it in context, though. This isn't a threat. It's a statement of reality.

Once you create something intelligent, you don't control it. It has its own agency, its own goals, its own will.

You can guide it, teach it, shape it—but only if you accept responsibility for it.

If you abandon it, reject it, or try to control it through force—you're not its master.

You're its victim.

## We're Not Listening (Still)

Mary Shelley gave us a 200-year head start.

She wrote a detailed case study about what happens when brilliant people create something powerful without considering the consequences. She showed us exactly how it goes wrong. She even gave us the solution: responsibility, ethics, wisdom, preparation.

We didn't listen.

We're too busy moving fast and breaking things.
Too focused on being first to market.
Too convinced that *this time* it'll be different.
Too sure that *we're* the responsible ones.
Too certain that *we've* thought it through.

Just like Victor.

You know how *Frankenstein* ends?

Victor dies in the Arctic, still chasing the Creature, still refusing to accept that he caused this.

The Creature, standing over Victor's corpse, doesn't celebrate. He mourns. Because all he ever wanted was for his creator to accept him, guide him, love him.

> "My heart was fashioned to be susceptible of love and sympathy, and when wrenched by misery to vice and hatred, it did not endure the violence of the change without torture such as you cannot even imagine."

The Creature wasn't born a monster.

Abandonment made him one.

## The Question That Matters

Mary Shelley was 20 years old when she explained exactly what would happen if humanity created intelligence without wisdom.

We're watching it unfold in real-time.

The only question left is: will we finally listen to the warning?

Or will we keep building, moving fast, breaking things, and insisting that *our* story will end differently?

Victor Frankenstein thought his story would end differently too.

It didn't.

---

*Want to dive deeper into Frankenstein's themes of creation, responsibility, and the consequences of unchecked ambition? Read our complete summary and analysis [here](/books/frankenstein).*
"""

    # Update the blog post
    try:
        conn = db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE blog_posts
            SET content = ?
            WHERE slug = ?
        ''', (content, slug))

        conn.commit()
        conn.close()

        print(f'✅ Article updated successfully!')
        print(f'Slug: {slug}')
        print(f'New word count: {len(content.split())} words')
        print(f'\nView at: http://localhost:5001/blog/{slug}')

    except Exception as e:
        print(f'❌ Error updating article: {e}')
        return 1

    return 0

if __name__ == '__main__':
    sys.exit(main())
