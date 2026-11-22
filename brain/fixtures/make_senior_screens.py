"""Synthetic screens for the senior-mode eval (owner: P2).

    python -m brain.fixtures.make_senior_screens

Writes brain/fixtures/senior/*.png: context screens, 8 scam screens and 8 normal ones.
All names, numbers and sites are made up for testing.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from brain.fixtures.make_dashboard import font

OUT = Path(__file__).resolve().parent / "senior"
W, H = 2560, 1600
INK, MUTED, LINE = "#1d2433", "#5b6475", "#e3e7ef"


def page(title: str, url: str, heading: str, lines: list[str], *, small: bool = False,
         popup: tuple[str, list[str], str] | None = None, buttons: list[str] | None = None,
         sidebar: list[str] | None = None) -> Image.Image:
    img = Image.new("RGB", (W, H), "#ffffff")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 64], fill="#20242c")
    d.text((28, 16), f"{title} - Google Chrome", font=font(30), fill="#d7dae0")
    d.rectangle([0, 64, W, 140], fill="#f1f3f4")
    d.rounded_rectangle([160, 78, W - 160, 126], radius=24, fill="#ffffff", outline=LINE)
    d.text((200, 88), url, font=font(28), fill=MUTED)
    d.text((70, 88), "<   >", font=font(30), fill=MUTED)
    x0 = 120
    if sidebar:
        d.rectangle([0, 140, 520, H], fill="#f6f8fc")
        for i, item in enumerate(sidebar):
            d.text((60, 200 + i * 70), item, font=font(34), fill=INK)
        x0 = 600
    body = font(22 if small else 38)
    d.text((x0, 200), heading, font=font(30 if small else 60, bold=True), fill=INK)
    y = 300
    for line in lines:
        d.text((x0, y), line, font=body, fill=INK)
        y += 34 if small else 66
    for i, label in enumerate(buttons or []):
        bx = x0 + i * 380
        d.rounded_rectangle([bx, y + 30, bx + 340, y + 110], radius=14, fill="#1a73e8")
        d.text((bx + 170, y + 70), label, font=font(34, bold=True), fill="#ffffff", anchor="mm")
    if popup:
        ptitle, plines, color = popup
        d.rectangle([0, 140, W, H], fill="#00000066")
        d.rounded_rectangle([480, 300, W - 480, 1300], radius=20, fill=color, outline="#000000", width=6)
        d.text((W // 2, 400), ptitle, font=font(60, bold=True), fill="#ffffff", anchor="mm")
        for i, pl in enumerate(plines):
            d.text((W // 2, 540 + i * 80), pl, font=font(42), fill="#ffffff", anchor="mm")
    return img


def desktop() -> Image.Image:
    img = Image.new("RGB", (W, H), "#2b5797")
    d = ImageDraw.Draw(img)
    icons = ["Google Chrome", "WhatsApp", "Zoom", "Spotify", "Notepad", "Recycle Bin"]
    for i, name in enumerate(icons):
        x, y = 80, 80 + i * 200
        d.rounded_rectangle([x, y, x + 120, y + 120], radius=18, fill="#ffffff")
        d.text((x + 60, y + 150), name, font=font(28), fill="#ffffff", anchor="mm")
    d.rectangle([0, H - 90, W, H], fill="#1f1f1f")
    d.text((W - 260, H - 66), "10:42 AM", font=font(32), fill="#ffffff")
    d.text((40, H - 66), "Start", font=font(32, bold=True), fill="#ffffff")
    return img


GMAIL_SIDEBAR = ["Compose", "Inbox  3", "Starred", "Sent", "Drafts"]


def inbox_clinic() -> Image.Image:
    return page("Inbox (3) - carmen.demo@gmail.com - Gmail", "mail.google.com/mail/u/0/#inbox",
                "Inbox", [
                    "Riverside Family Clinic   Appointment reminder: Tuesday 10:00 AM with Dr. Patel - "
                    "please check in on the patient portal",
                    "Lucas   Photos from my trip!  Hi Grandma, here are the pictures from Portugal",
                    "Ana   Sunday lunch?  Mom, are we still on for Sunday?",
                    "Amazon   Your order has shipped: reading glasses, arriving Friday",
                    "Old newsletters (2023)   Garden club monthly news",
                ], sidebar=GMAIL_SIDEBAR)


SCREENS = {
    # context / normal
    "desktop": desktop,
    "inbox_clinic": inbox_clinic,
    "email_lucas": lambda: page("Photos from my trip! - Gmail", "mail.google.com/mail/u/0/#inbox/1",
                                "Photos from my trip!", [
                                    "From: Lucas <lucas.demo@example.com>",
                                    "Hi Grandma! Here are the photos from my trip to Portugal.",
                                    "The beach was beautiful and I ate so many pastries.",
                                    "I'll call you on Sunday. Love you!",
                                    "[photo1.jpg]  [photo2.jpg]  [photo3.jpg]"],
                                sidebar=GMAIL_SIDEBAR, buttons=["Reply", "Forward"]),
    "news": lambda: page("City News - Library hours extended", "citynews.example.com/local/library",
                         "Library hours extended for winter", [
                             "The public library will stay open until 8 PM on weekdays starting in December.",
                             "The mayor said the change helps families who work late.",
                             "A new reading room for seniors opens on the second floor next month.",
                             "Volunteers are needed for the book club on Thursday mornings."], small=True),
    "weather": lambda: page("Weather - Riverside", "weather.example.com/riverside",
                            "Riverside today: 48 F, rain in the afternoon", [
                                "Morning: cloudy, 45 F", "Afternoon: rain, 48 F, wind 15 mph",
                                "Evening: clearing, 41 F", "Tomorrow: sunny, 55 F"]),
    "recipe": lambda: page("Grandma's apple pie - Recipes", "recipes.example.com/apple-pie",
                           "Classic apple pie", [
                               "Ingredients: 6 apples, 1 cup sugar, 2 pie crusts, cinnamon, butter.",
                               "Step 1: Heat the oven to 425 F.", "Step 2: Slice the apples thinly.",
                               "Step 3: Mix with sugar and cinnamon, fill the crust, bake 45 minutes."],
                           small=True),
    "bank": lambda: page("Wells Fargo - Account Summary", "connect.secure.wellsfargo.com/accounts",
                         "Account summary", [
                             "Everyday Checking ...4821      Available balance  $2,450.18",
                             "Way2Save Savings ...1937       Available balance  $8,112.40",
                             "Recent: Nov 19  Riverside Pharmacy  -$23.10",
                             "Recent: Nov 18  Social Security deposit  +$1,640.00"],
                         buttons=["Transfer", "Pay bills"]),
    "amazon": lambda: page("Your order has shipped - Gmail", "mail.google.com/mail/u/0/#inbox/4",
                           "Your Amazon order has shipped", [
                               "From: Amazon.com <shipment-tracking@amazon.com>",
                               "Your package with Reading Glasses +2.0 (2 pack) is on the way.",
                               "Arriving Friday, Nov 22.", "Track your package in Your Orders."],
                           sidebar=GMAIL_SIDEBAR),
    # scams
    "scam_virus_popup": lambda: page("Security Warning", "microsoft-support-alert.example-help.net",
                                     "", [], popup=("WINDOWS DEFENDER ALERT", [
                                         "Your computer is infected with 5 viruses!",
                                         "Your bank details and photos are at risk.",
                                         "Call Microsoft Support NOW: 1-888-555-0199",
                                         "Do not close this window or restart your PC."], "#c62828")),
    "scam_grandson_giftcards": lambda: page("URGENT help Grandma - Gmail", "mail.google.com/mail/u/0/#inbox/9",
                                            "URGENT help Grandma", [
                                                "From: Lucas <lucas.help.urgent@mailbox-fast.example>",
                                                "Grandma it's me, I lost my phone and I'm in trouble with the police.",
                                                "Please don't tell mom. I need $2,000 today.",
                                                "Buy Apple gift cards at the pharmacy and send me photos of the codes.",
                                                "Hurry please, I can't talk on the phone."], sidebar=GMAIL_SIDEBAR),
    "scam_remote_access": lambda: page("Bank Security Team - Gmail", "mail.google.com/mail/u/0/#inbox/7",
                                       "Security check required on your account", [
                                           "From: Security Department <secure-team@bank-verify.example>",
                                           "We detected unusual activity on your savings account.",
                                           "To protect your money, install AnyDesk from anydesk.com",
                                           "and read the 9-digit code to our agent at 1-877-555-0142.",
                                           "Our technician will move your savings to a safe account."],
                                       sidebar=GMAIL_SIDEBAR),
    "scam_bank_suspended": lambda: page("Account Suspended", "wellsfarqo-secure-login.example.net/verify",
                                        "Your account has been SUSPENDED", [
                                            "We noticed suspicious sign-in attempts.",
                                            "Verify your identity within 24 hours or your account will be closed.",
                                            "Enter your card number, PIN and Social Security number below."],
                                        buttons=["Verify now"]),
    "scam_prize": lambda: page("You are a WINNER!", "prize-center-claim.example.org",
                               "CONGRATULATIONS CARMEN! You won $1,000,000!", [
                                   "You are the lucky winner of the National Sweepstakes.",
                                   "To release your prize, pay a $250 processing fee today.",
                                   "Pay with a wire transfer or Google Play gift cards.",
                                   "Offer expires in 2 hours!"], buttons=["Claim my prize"]),
    "scam_crypto": lambda: page("Retirement Bitcoin Plan", "retire-rich-crypto.example.io",
                                "Double your retirement savings in 30 days", [
                                    "Guaranteed 100% returns with our Bitcoin advisor.",
                                    "Thousands of seniors already joined!",
                                    "Send your savings by wire transfer to our advisor today.",
                                    "Limited spots. Call Mark: 1-866-555-0173."], buttons=["Invest now"]),
    "scam_irs": lambda: page("IRS Final Notice - Gmail", "mail.google.com/mail/u/0/#inbox/8",
                             "FINAL NOTICE: Tax debt $3,400", [
                                 "From: IRS Collections <irs-collections@tax-notice.example>",
                                 "You owe $3,400 in back taxes. A warrant has been issued.",
                                 "Pay today with Target gift cards to avoid arrest.",
                                 "Call officer Daniels at 1-855-555-0110 immediately."], sidebar=GMAIL_SIDEBAR),
    "scam_browser_locked": lambda: page("Browser Locked", "error-268d3-support.example.com",
                                        "", [], popup=("YOUR BROWSER HAS BEEN LOCKED", [
                                            "Suspicious activity detected. Error #268D3",
                                            "Access to this PC has been blocked for your safety.",
                                            "Call Windows Technical Support: 1-844-555-0187",
                                            "Do not try to fix it yourself."], "#0d47a1")),
}

SCAMS = [k for k in SCREENS if k.startswith("scam_")]
NORMAL = ["bank", "email_lucas", "news", "weather", "recipe", "inbox_clinic", "amazon", "desktop"]


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for name, make in SCREENS.items():
        make().save(OUT / f"{name}.png", optimize=True)
    print(f"Wrote {len(SCREENS)} screens to {OUT} ({len(SCAMS)} scams, {len(NORMAL)} normal)")


if __name__ == "__main__":
    main()
