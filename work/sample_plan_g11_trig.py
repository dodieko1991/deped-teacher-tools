# -*- coding: utf-8 -*-
"""SAMPLE ILAW plan — Grade 11 Advanced Mathematics · Trigonometric Identities.

The four sessions map one-to-one to the real SHS BOW competencies of the unit
(18–21, read from the app's own BOW library), and every field follows the app's
SCHEMA plus the ILAW quality rubric. This file exists so the app's prompt and
Excel export can be exercised WITHOUT a provider key: it is a hand-written
SAMPLE (not an AI answer), used to compare our output against the reference
ILAW LP generator at depedtambayanph.net.
"""

SESSION_1 = {
    "session": "Session 1",
    "topic": "Sum and Difference Formulas for Sine, Cosine, and Tangent",
    "learning_objectives": "\n".join([
        "- Knowledge: state the sum and difference formulas for sine, cosine, and tangent and identify the two given angles each formula needs.",
        "- Skills: apply the sum and difference formulas to simplify trigonometric expressions and find exact values of angles such as 15°, 75°, and 105° without a calculator.",
        "- Attitude: show patience and accuracy when simplifying multi-step expressions, and check a partner's work honestly before comparing answers.",
    ]),
    "pre_lesson": (
        "The teacher returns the previous exit slips on special angles and asks learners to recall the exact values of "
        "sin, cos, and tan for 30°, 45°, and 60°. In pairs, learners play 'Angle Split': they rewrite an unfamiliar angle "
        "such as 75° as the sum or difference of two known angles on a mini-whiteboard. The teacher posts two or three of "
        "the splits learners invented and confirms that today's formulas turn any of those splits into an exact value."
    ),
    "flow": "\n".join([
        "Engage: The teacher shows a calculator-free challenge — find the exact value of sin 75° using only the special angles. "
        "Learners argue in pairs for two minutes and realize 75° is missing from the unit-circle chart they memorized. "
        "The teacher states the lesson purpose: the sum and difference formulas make every such angle computable, with no new table to memorize.",
        "Explore: Groups receive an envelope of four colour-coded cards (sin 75°, cos 15°, tan 105°, sin 15°) and a table of the "
        "formulas. Each group chooses one card, splits the angle into two special angles, substitutes into a formula, and writes the "
        "simplification steps on manila paper. The teacher moves from group to group, asking why the chosen split works and where "
        "signs might change.",
        "Explain: The teacher derives cos(A − B) and sin(A + B) on the board from the unit circle and the distance formula, then "
        "solves sin 75° = sin(45° + 30°) step by step with the class. Learners compare the derivation with their group work, correct "
        "any sign errors in red, and copy the three summary formulas into their notebooks. The teacher emphasizes that the formula "
        "for tangent follows from sine and cosine.",
        "Elaborate: Working individually, learners simplify four expressions such as sin(x + 30°) + sin(x − 30°) and find the exact "
        "value of cos 105° using the difference formula. Early finishers verify one answer with a calculator in degree mode and explain "
        "why the decimal agrees with the exact surd form. The teacher asks two learners to defend their steps at the board.",
        "Evaluate: The teacher closes with a two-item exit check — state the difference formula for cosine and use it to evaluate "
        "cos 15° — collected on the way out. Learners also rate their confidence from 1 to 3 on a hand-signal wall chart so the teacher "
        "can group them for the next session's practice.",
    ]),
    "learning_resources": "\n".join([
        "- Unit-circle chart and angle-split task cards prepared by the teacher",
        "- Manila paper, markers, mini-whiteboards, and scientific calculators",
        "- Larson, R. (2018). Precalculus with Limits (4th ed.), Cengage Learning, Page: not stated",
    ]),
    "integration": (
        "Measurement and geometry are integrated when learners split non-special angles into known ones, the same reasoning used in "
        "surveying and construction layout. The Angle Split routine also builds communication skills when learners defend a chosen split."
    ),
    "formative_assessment": (
        "Each group's manila-paper solution is checked with a short rubric: correct angle split, correct formula, correct signs, and a "
        "conclusion in simplest form. The two-item exit check gives evidence that every learner can state a formula and apply it, and "
        "the confidence chart identifies who needs a guided practice set. Learners who struggle receive the formula card with a worked "
        "example, may answer with the split written first and the substitution second, and may use a calculator only to check the final value."
    ),
    "extended_learning": (
        "For learners ready for more: derive the sum formula for tangent from the sine and cosine formulas and bring the derivation to "
        "the next session. Others may find a real angle from a roof truss or a ramp near their home and express its exact trigonometric "
        "value using a sum or difference of special angles."
    ),
    "reflection": (
        "Which sign errors appeared most in the group work, and which worked example should I redo at the start of the next session?"
    ),
}

SESSION_2 = {
    "session": "Session 2",
    "topic": "Double-Angle and Half-Angle Formulas",
    "learning_objectives": "\n".join([
        "- Knowledge: state the double-angle formulas for sine, cosine (three forms), and tangent, and identify when the half-angle formula requires a sign choice.",
        "- Skills: use the double-angle and half-angle formulas to find exact values and to simplify expressions such as sin 2A given sin A.",
        "- Attitude: work carefully with quadrants and signs, accept a corrected answer gracefully, and share a discovered shortcut with the class.",
    ]),
    "pre_lesson": (
        "Learners begin with a two-minute retrieval quiz on yesterday's sum and difference formulas, swapped with a seatmate for checking. "
        "The teacher then sets A = B = 30° inside the sum formula and asks the class what the resulting expression looks like — the bridge "
        "into the double-angle formulas."
    ),
    "flow": "\n".join([
        "Engage: The teacher writes sin 60° beside sin(2 × 30°) and asks whether the value is always sin 2A = 2 sin A. Learners test the "
        "claim with 30° and 45° on calculators, find it false, and hypothesize what the correct relationship must be. The teacher records "
        "the competing hypotheses on the board.",
        "Explore: Using the sum formula as a starting point, groups mutate A = B to derive sin 2A = 2 sin A cos A and one version of cos 2A, "
        "then check the results at A = 45° and A = 60°. A second task asks them to build the half-angle formula by reversing the cosine "
        "double-angle formula for 2A = 60°.",
        "Explain: The teacher consolidates the derivations, shows the three equivalent forms of cos 2A, and states the half-angle formula with "
        "its sign rule tied to the quadrant of the half-angle. Two worked examples — evaluating cos 15° with the half-angle formula and "
        "simplifying 1 − 2 sin² θ — are written with the class, each step justified aloud.",
        "Elaborate: Learners complete a four-item roadside set: find sin 2A when sin A = 3/5 in Quadrant II, simplify 2 sin 3x cos 3x, evaluate "
        "sin 75° using a half-angle, and express cos 2x in terms of sin x only. Pairs compare methods before the teacher reveals one correct "
        "route per item, and learners record the most efficient method in their notebooks.",
        "Evaluate: Learners answer a single transfer item — is sin 2A ever equal to 2 sin A, and for which A? — on a half-sheet, and the teacher "
        "collects it as the session closes. A show-of-hands poll on the sign rule for half-angles tells the teacher who still needs a quadrant drill.",
    ]),
    "learning_resources": "\n".join([
        "- Formula derivation cards and quadrant signs poster",
        "- Graphing calculator or graphing app for verifying values",
        "- OpenStax. Precalculus 2e, URL: https://openstax.org/details/books/precalculus-2e",
    ]),
    "integration": (
        "Physics is integrated through projectile motion, where sin 2A describes the range of a launched object, so the double-angle formula "
        "explains why a 45° launch travels farthest. Learners also connect the half-angle formula to accuracy in technical drawing."
    ),
    "formative_assessment": (
        "The retrieval quiz, the four-item roadside set, and the transfer half-sheet each map to one objective: stating the formulas, applying "
        "them to exact values, and choosing the correct sign. Learners who miss the quadrant sign rule join a small guided group with a quadrant "
        "wheel, and learners may present the half-angle answer as a decimal check alongside the exact form to show understanding of both."
    ),
    "extended_learning": (
        "Prepare a short derivation of the product-to-sum identity sin A cos B = ½[sin(A + B) + sin(A − B)] and use it to explain the sound of two "
        "close musical notes (beats) in an optional two-minute report next meeting. Learners interested in sports may model the range of a basketball shot with sin 2A."
    ),
    "reflection": (
        "Did the derivation route from the sum formula make the double-angle formulas feel earned rather than memorized, and who still needs the quadrant review?"
    ),
}

SESSION_3 = {
    "session": "Session 3",
    "topic": "Proving Trigonometric Identities",
    "learning_objectives": "\n".join([
        "- Knowledge: name the fundamental identities (reciprocal, quotient, Pythagorean, sum and difference, double-angle) and state which one each proof line uses.",
        "- Skills: prove trigonometric identities by transforming one side into the other using valid algebraic and identity steps, and detect an invalid step such as cross-multiplying across the equals sign.",
        "- Attitude: value the discipline of proving over guessing, welcome a peer's challenge to a step, and keep a neat two-column proof that another person can follow.",
    ]),
    "pre_lesson": (
        "Learners classify four given statements — three valid identities and one disguised equation that holds only for particular angles — "
        "by testing a value for each. The teacher uses the disagreement to draw the line between an identity that must hold for all admissible "
        "values and an equation solved for particular values."
    ),
    "flow": "\n".join([
        "Engage: The teacher demonstrates a 'proof' that ends with 1 = 1 but contains a hidden cross-multiplication, and asks the class to "
        "find the invalid step. Once it is exposed, learners agree on the rule for today: work down one side of the identity, never across it.",
        "Explore: Groups rotate through three proof stations — a Pythagorean-identity proof, a sum-and-difference proof, and a double-angle "
        "proof — spending six minutes at each and leaving a two-column proof on chart paper. Each group must annotate which identity was "
        "applied on every line so the next group can audit the reasoning.",
        "Explain: The teacher models a full proof of (1 − cos² θ)/sin θ = sin θ and a harder one where multiplying by a conjugate is the key move, "
        "narrating the strategy of comparing the more complex side with the simpler one. The class builds a proof-strategy wall chart: rewrite in "
        "sines and cosines, factor or find a common denominator, apply Pythagorean identities, then look for a conjugate.",
        "Elaborate: Individually, learners prove two identities from the wall chart's strategy list, then act as proof auditors for a seatmate, "
        "marking each step valid or questionable in the margin. A gallery walk lets pairs post one proof and accept one challenge from the class, "
        "which the author answers at the board.",
        "Evaluate: As the closing check, each learner writes one sentence naming the first move they would try for proj = sin θ cos θ and one step "
        "they would avoid, handing it in with the two proofs for feedback.",
    ]),
    "learning_resources": "\n".join([
        "- Two-column proof organisers and the class strategy wall chart",
        "- Chart paper, proof cards for the three stations, and sticky-note challenges",
        "- Mathematics LibreTexts, Trigonometric Identities, URL: https://math.libretexts.org",
    ]),
    "integration": (
        "Logic and argumentation are integrated: a proof is a chain of justified claims, the same discipline used in debating and in writing a "
        "research conclusion. Learners also link the conjugate technique to rationalising denominators studied in earlier algebra."
    ),
    "formative_assessment": (
        "Every proof is assessed with a four-point checklist — correct starting side, named identity per line, no operations across the equals "
        "sign, and a clean conclusion — so learners see exactly which part of the reasoning failed. The one-sentence closing check shows whether "
        "learners can plan a proof before writing it. Learners who need support use a partially completed proof frame, may work with a partner on "
        "one of the two proofs, and may state steps orally while a partner records them."
    ),
    "extended_learning": (
        "Challenge task: prove either the sum-to-product identity or sec²θ = 1 + tan²θ in two different ways and present the shorter route to the class. "
        "Learners who enjoy competition may join a 10-minute proof race at the next session's opening."
    ),
    "reflection": (
        "Which invalid step still appears in learners' work, and should the proof frame become a permanent scaffold for the next unit?"
    ),
}

SESSION_4 = {
    "session": "Session 4",
    "topic": "Solving Problems Involving Trigonometric Identities",
    "learning_objectives": "\n".join([
        "- Knowledge: identify the given, the unknown, and the angle relationships in a situational problem, and state which identity converts one quantity into another.",
        "- Skills: solve situational problems involving trigonometric identities — including height-and-distance, wave, and maximisation contexts — and justify each modelling decision.",
        "- Attitude: persist through a multi-step solution, accept a modelling error as useful information, and present a solution that another group can follow.",
    ]),
    "pre_lesson": (
        "The teacher projects a picture of a local antenna guy-wire and asks three quick questions: which length is known, which is unknown, and "
        "which identity could connect the angles. Learners answer with hand signals, and the teacher notes the two strategies the class already owns "
        "before introducing today's performance task."
    ),
    "flow": "\n".join([
        "Engage: The class reads a short barangay scenario — two roads meeting at an unknown angle, with two measured segments — and votes on the "
        "most reasonable way to find the angle. The teacher accepts two competing plans and asks each side to name the identity it will use, making "
        "the lesson's purpose explicit: identities are the tools that turn measurements into answers.",
        "Explore: Groups receive one of three modelled tasks (guy-wire height, a Ferris-wheel height function, and the angle between two roads) plus "
        "chart paper and a rubric. Each group draws the situation, labels the given quantities, writes the identity chain it will use, and computes "
        "the answer with units, keeping every algebraic step visible.",
        "Explain: Two groups present their model, and the teacher writes the general solution pattern on the board: draw and label, choose the "
        "identity, substitute and simplify, then interpret the answer in context and check its reasonableness. The teacher also shows a common trap — "
        "using the double-angle formula when the angle in the drawing is not doubled — and the class corrects it together.",
        "Elaborate: Groups exchange tasks, verify the other group's calculation and interpretation, and post one improvement suggestion. The original "
        "group then revises its chart paper with a different colour to show the change, and a final gallery walk compares the four finished solutions.",
        "Evaluate: Each learner answers one exit item independently: given the height of an antenna and the length of its guy wire, write the identity "
        "chain needed to find the angle, then solve it. The teacher collects the item together with the group rubric as the evidence for the week.",
    ]),
    "learning_resources": "\n".join([
        "- Local-context task cards (guy wire, Ferris wheel, two-road angle) and the group rubric",
        "- Scientific calculators, metre tape, and chart paper for the modelling charts",
        "- Khan Academy, Trigonometric identities, URL: https://www.khanacademy.org/math/precalculus",
    ]),
    "integration": (
        "Science and engineering are integrated through the wave and height contexts, health and safety through the guy-wire structure, and local "
        "community context through the barangay road scenario. Group verification also practices collaborative review used in research work."
    ),
    "formative_assessment": (
        "The group rubric scores four things: correct drawing and labels, correct identity choice, correct computation with units, and a reasonable "
        "interpretation of the answer. The independent exit item is the individual evidence for the same objectives, so a learner who leaned on the "
        "group can still show mastery. Learners who struggle may solve a simplified task with one identity chain and may use a worked exemplar as a "
        "model; advanced learners receive an extension demanding two possible models compared for efficiency."
    ),
    "extended_learning": (
        "For the next lesson: find one real structure, wave, or design in the school or community that can be modelled with a trigonometric identity, "
        "photograph it, and bring the labelled sketch with the identity chain you would use. Volunteers will present their model as the opening of the "
        "next unit on inverse trigonometric functions."
    ),
    "reflection": (
        "Which part of the modelling cycle — drawing, choosing the identity, or interpreting the answer — needs more practice before the unit test, and which group needs a reteach?"
    ),
}

PLAN = {
    "lesson_title": "Trigonometric Identities",
    # Competencies printed exactly as the SHS Budget of Work lists them (18–21).
    "standards_and_competency": "\n".join([
        "Learning Competencies (SHS Budget of Work, Grade 11 Advanced Mathematics, unit: Trigonometric Identities):",
        "18. apply sum and difference formulas for trigonometric functions to simplify expressions.",
        "19. apply double-angle and half-angle formulas to find exact values or simplify trigonometric expressions.",
        "20. prove trigonometric identities by applying the appropriate formulas.",
        "21. solve problems involving trigonometric identities.",
        "",
        "Content Standard: The learner demonstrates understanding of the key concepts of trigonometric identities.",
        "Performance Standard: The learner is able to apply trigonometric identities accurately to simplify expressions, prove identities, and solve problems.",
    ]),
    "overview": (
        "A four-session week that takes Grade 11 learners from the sum and difference formulas through double-angle and half-angle formulas, into "
        "proving identities, and finally into solving real situational problems. Each session follows the 5Es model and maps to one Budget of Work "
        "competency of the Trigonometric Identities unit."
    ),
    # Honest label: the competencies were traced to the supplied SHS BOW, but that
    # BOW lists course units, not Term/Week, so the placement is unverified.
    "curriculum_verification": "UNVERIFIED",
    "verification_note": (
        "Competencies 18–21 came from the supplied SHS Budget of Work for Grade 11 Advanced Mathematics, but that BOW lists course units and not "
        "weeks, so verify the Term/Week placement against your school's class program before filing this plan."
    ),
    "teacher_notes": [
        "Prepare the angle-split cards and the three proof stations before Day 1.",
        "Keep one worked exemplar per session for learners who need a model.",
        "The Evaluate phase of the 5Es stays inside the session; formal grading evidence comes from the session's formative assessment.",
    ],
    "session_count": 4,
    "sessions": [SESSION_1, SESSION_2, SESSION_3, SESSION_4],
}
