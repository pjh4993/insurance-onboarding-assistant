// Drives the customer app (/s/{token}) the way a person would, answering whatever the chat asks next.
import { expect, type Locator, type Page } from "@playwright/test";
import { t, type Locale } from "./i18n";
import { OTP, otpFor, type Seed } from "./seeds";

type Step = "identity" | "otp" | "needs" | "parties" | "answers" | "decision" | "confirm" | "closed" | "waitAgent";

export class CustomerApp {
  constructor(
    readonly page: Page,
    public locale: Locale,
  ) {}

  m(key: string, params?: Record<string, string | number>) {
    return t(this.locale, key, params);
  }

  // ---- landing

  headline() {
    return this.page.getByRole("heading", { level: 1 });
  }

  localeOption(locale: Locale) {
    return this.page.getByRole("radio", { name: t(locale, `common.localeName.${locale}`) });
  }

  async switchLocale(locale: Locale) {
    await this.localeOption(locale).click();
    await expect(this.localeOption(locale)).toHaveAttribute("aria-checked", "true");
    this.locale = locale;
  }

  async startWithoutProduct() {
    await this.page.getByRole("button", { name: this.m("customer.startPlain") }).click();
  }

  productCard(market: string, product: string) {
    return this.page.getByRole("button", { name: new RegExp(escape(this.m(`products.${market}.${product}.name`))) });
  }

  // ---- chat controls

  private controls(): Record<Step, Locator> {
    const p = this.page;
    const composer = (kind: string) => p.getByPlaceholder(this.m(`input.placeholder.${kind}`));
    return {
      // The customer chat asks identity one field at a time (a stepped topic form); NEEDS forms come with a
      // free-text composer, which the flows below answer instead.
      identity: p.locator('.stepper[data-type="IDENTITY_INFO"] .btn--cta'),
      otp: p.getByLabel(this.m("otp.label")), // its button stays disabled until a code is typed
      needs: composer("NEEDS"),
      parties: composer("PARTIES"),
      answers: composer("ANSWERS"),
      decision: p.getByRole("button", { name: this.m("decision.accept") }).first(),
      confirm: p.getByRole("button", { name: this.m("confirm.submit") }),
      closed: p.locator(".input-panel--closed"),
      waitAgent: p.getByText(this.m("input.waitAgent")),
    };
  }

  /**
   * Which input the chat is waiting for now. While a turn runs the typing indicator shows and the previous
   * step's controls stay on screen, so this waits for the indicator to go, then takes the first control that is
   * enabled (closed and wait-for-agent are notices).
   */
  async currentStep(): Promise<Step> {
    let found: Step | null = null;
    await expect
      .poll(async () => {
        if (await this.page.locator(".typing").isVisible()) return null;
        for (const [step, loc] of Object.entries(this.controls()) as [Step, Locator][]) {
          const el = loc.first();
          if (!(await el.isVisible())) continue;
          if (step === "closed" || step === "waitAgent" || (await el.isEnabled())) return (found = step);
        }
        return null;
      })
      .not.toBeNull();
    return found!;
  }

  needsBox() {
    return this.controls().needs;
  }

  /** The stepped identity form (contact, ID document, consent). */
  identityForm() {
    return this.page.locator('.stepper[data-type="IDENTITY_INFO"]');
  }

  private assistantReplies() {
    return this.page.locator(".msg--assistant .msg__bubble:not(.typing)");
  }

  /** Runs `act`, then waits for the assistant's reply (or the session to close) before returning. */
  private async andWaitForReply(act: () => Promise<void>) {
    const before = await this.assistantReplies().count();
    await act();
    await expect
      .poll(async () => (await this.assistantReplies().count()) > before || (await this.controls().closed.isVisible()))
      .toBe(true);
  }

  /**
   * Answers the identity topic forms (contact, ID document, consent) one question at a time, until the chat
   * asks for something else. Inputs carry the field's name; choice buttons carry the option's value.
   */
  async fillIdentity(seed: Seed, { consent }: { consent: boolean }) {
    const values: Record<string, string | boolean> = {
      full_name: seed.full_name,
      email: seed.email,
      phone: seed.phone,
      id_document_type: seed.id_document_type,
      id_document_number: seed.id_document_number,
      third_party_consent: consent,
    };
    const form = this.identityForm();
    // Each turn waits for the chat to settle, so a form that is about to be replaced is never answered.
    for (let i = 0; i < 12 && (await this.currentStep()) === "identity"; i++) {
      const field = form.locator(".stepper__field");
      // The last question of a topic sends the form, and the assistant answers it.
      const sends = async () => {
        const dots = form.locator(".stepper__progress span");
        return (await dots.count()) === (await form.locator(".stepper__progress .done").count()) + 1;
      };
      const act = async (run: () => Promise<void>) => {
        if (!(await sends())) return run();
        // Wait for the assistant's reply and for this form to go (the next topic's form, or another step).
        const sent = await form.elementHandle();
        await this.andWaitForReply(run);
        await expect.poll(() => sent!.evaluate((n) => n.isConnected)).toBe(false);
      };
      const choices = field.locator(".choice");
      if (await choices.count()) {
        const name = await field.getAttribute("data-field");
        await act(() => field.locator(`.choice[data-value="${values[name ?? ""]}"]`).click());
        continue;
      }
      const box = field.locator("input").first();
      const name = (await box.getAttribute("name")) ?? "";
      if ((await box.getAttribute("type")) === "checkbox") await box.setChecked(values[name] === true);
      else await box.fill(String(values[name] ?? ""));
      await act(() => this.controls().identity.click());
    }
  }

  async enterOtp(code = OTP) {
    await this.controls().otp.fill(code);
    await this.andWaitForReply(() => this.page.getByRole("button", { name: this.m("otp.submit"), exact: true }).click());
  }

  async say(step: "needs" | "parties" | "answers", text?: string) {
    const box = this.controls()[step];
    await expect(box).toBeEnabled();
    if (text !== undefined) await box.fill(text);
    await this.andWaitForReply(() => this.page.getByRole("button", { name: this.m("input.send") }).click());
  }

  async acceptFirstOffer() {
    await this.andWaitForReply(() => this.controls().decision.click());
  }

  async confirm() {
    await this.andWaitForReply(() => this.controls().confirm.click());
  }

  /**
   * Answers every question with the seed's data until the session closes or waits for an agent, and returns
   * where it stopped. Identity must already be done or be the current step.
   */
  async completeOnboarding(seed: Seed, { consent = false, maxSteps = 15 } = {}): Promise<"closed" | "waitAgent"> {
    for (let i = 0; i < maxSteps; i++) {
      const step = await this.currentStep();
      switch (step) {
        case "identity":
          await this.fillIdentity(seed, { consent });
          break;
        case "otp":
          await this.enterOtp(otpFor(seed));
          break;
        case "needs":
          await this.say("needs", seed.needs_text);
          break;
        case "parties":
          await this.say("parties", "Just me");
          break;
        case "answers":
          await this.say("answers", "Here are my details."); // the mock answers for each seed customer
          break;
        case "decision":
          await this.acceptFirstOffer();
          break;
        case "confirm":
          await this.confirm();
          break;
        default:
          return step;
      }
    }
    throw new Error(`still onboarding after ${maxSteps} steps`);
  }

  closedNotice(statusKey: string) {
    return this.page.getByText(this.m("input.closed", { status: this.m(`status.${statusKey}`) }));
  }
}

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
