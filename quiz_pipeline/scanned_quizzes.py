"""Hand-transcribed quizzes for the fully-scanned (image-only) written tests.
Question text read by eye from the rendered pages; correct answers from each
test's own answer key (handwritten key page for the 2014 Southwest tests, printed
key for the 2016 Tennessee test). Consumed by build_manual.py."""


def q(stem, choices, letter):
    idx = 'ABCDEF'.index(letter.upper())
    return {'text': stem, 'choices': [{'text': c, 'is_correct': j == idx} for j, c in enumerate(choices)]}


def qi(stem, choices, letter, image):
    """A parts-ID question carrying a diagram image (rendered to media/quiz_images
    by render_parts_images.py)."""
    d = q(stem, choices, letter)
    d['image_rel'] = 'quiz_images/' + image + '.png'
    return d


TF = ['True', 'False']

# ---- 2014 Southwest Regional FIELD (pk1114); handwritten key p0. q26 dropped
# (protested, "no correct answer"). q25 answer E (D crossed out on the key). ----
SW_FIELD = [
 q("During a rescue and recovery operation, one of the duties of the outside Supervisor is to:",
   ["Arrange for guards and state and/or local police.", "Notify all persons on the notification plan of the emergency.", "Obtain gas samples from the main exhaust.", "None of the above"], 'A'),
 q("The explosive range of Ethane in normal air is?", ["2.12 - 9.35%", "3.0 - 12.5%", "2.5 - 9.35%", "None of the above"], 'B'),
 q("Reestablishing ventilation and bringing fresh air to an area damaged by fire or explosion is the main task of mine rescue teams in a rescue operation.", TF, 'B'),
 q("The law requires that gas detectors be able to measure concentrations of methane from 0.0 to 90% of volume, oxygen from 0.0 to 20% of volume, and carbon monoxide from 0.0 to 9,999 ppm.", TF, 'B'),
 q("Air locking operations should never be undertaken until the oxygen content of the air behind the seals has been reduced to at least ___%.", ["2.0%", ".05%", "1%", "5.0%"], 'A'),
 q("Urethane foam should never be applied greater than ___ inch thick because of spontaneous combustion.", ["1/2 inch", "2 inch", "1 inch", "1 1/2 inch"], 'C'),
 q("You can allow a rescued miner to walk out of the mine alone if the miner appears to be in good shape?", TF, 'B'),
 q("Usually, after temporary seals are erected, a waiting period of about 48 hours is recommended before beginning construction on permanent seals?", TF, 'B'),
 q("When constructing a temporary bulkhead from a crosscut, the bulkhead should be ___ feet into the passageway?", ["10 to 12", "1 to 2", "4 to 6", "None of the above."], 'C'),
 q("The smoke tube is used to determine the direction and velocity of air moving above 120 feet per minute.", TF, 'B'),
 q("If you are exposed to high concentrations of CO, you may experience very few symptoms before losing consciousness.", TF, 'A'),
 q("Breathing air containing 5% Carbon Dioxide can increase respiration ___%.", ["500", "300", "150", "None of the above."], 'B'),
 q("___ is found after methane explosions in air having low oxygen content?", ["Butane", "Ethane", "Acetylene", "Argon"], 'C'),
 q("During the debriefing session the ___ will provide the information found during exploration?", ["Team Captain", "Co-Captain", "Fresh Air Base", "Team"], 'D'),
 q("Heavier gases such as carbon dioxide and sulfur dioxide do not diffuse rapidly, so they're easier to disperse?", TF, 'B'),
 q("The degree to which a toxic gas will affect you depends on three factors: 1) how concentrated the gas is 2) how explosive the gas is and 3) how long you're exposed to the gas?", TF, 'B'),
 q("The formula used to find the quantity of air moving through a drift is:",
   ["Quantity (ft3) = Area (ft2) x Velocity (ft/min.)", "Quantity (ft3) = Area (ft2) x Velocity (ft/sec.)", "Quantity (ft2) = Area (ft2) x Velocity (ft/min.)"], 'A'),
 q("Oxides of nitrogen are highly toxic. Breathing even small amounts will cause irritable bowel syndrome.", TF, 'B'),
 q("A line brattice is brattice cloth or plastic that is hung to channel intake air into a working area that otherwise would not have adequate ventilation.", TF, 'A'),
 q("3rd degree burns covering less than 10% of the body (not including hands, feet, or face) is considered low or third priority.", TF, 'B'),
 q("The team briefing is normally conducted:", ["Only at a mine rescue contest", "At the fresh air base", "Command Center", "None of the above"], 'C'),
 q("Rock-Strata gases commonly called “rock gas” is assumed to contain what two types of gasses?", ["Hydrogen and Carbon Monoxide", "Nitrogen and Sulfur Dioxide", "Nitrogen and Carbon Dioxide", "Hydrogen Sulfide and Hydrogen"], 'C'),
 q("Normally gasses do not stratify when the ventilation system in a mine is working properly.", TF, 'A'),
 q("In a multi-level mine, a tunnel driven perpendicular to the main vein system of the mine is considered a?", ["Drift", "Stope", "Crosscut", "None of the above"], 'C'),
 q("A main cause of oxygen deficiency in a mine is:", ["Insufficient ventilation", "Displacement by other gases", "A fire or explosion", "Consumption by workers", "All of the above."], 'E'),
 # q26 dropped — protested, no correct answer
 q("The advantage of progressive ventilation is it is a fast process.", TF, 'B'),
 q("Ventilation controls affect the amount of air that travel and the direction of flow.", TF, 'A'),
 q("A fresh air base is usually established at a point where conditions no longer permit barefaced exploration.", TF, 'A'),
 q("The command center for rescue and recovery operations is generally only consisting of federal and state officials?", TF, 'B'),
]

# ---- 2014 Southwest Regional TECHNICIAN Drager BG4 (pk1117); handwritten key p0.
# Dropped: q4 & q6 (answer depends on a circled diagram), q10 (key blank, "not a
# good question"), q11 & q21 (protested / ambiguous key marks). ----
SW_BG4 = [
 q("Name the area/s in which the medium pressure is used?", ["Dosage line", "Emergency bypass", "Minimum valve", "a. and c."], 'D'),
 q("A major component group of the BG4 is the:", ["reducer", "breathing bag", "Pneumatics", "dosage line"], 'C'),
 q("The high pressure leak test (OCR/CCR) when using the Monitron or Sentinel will:",
   ["check leak tightness and dosage flow", "determine cylinder pressure and minimum valve activation", "ensure cylinder pressure is < 2600 PSI", "none of the above"], 'C'),
 q("Two low pressure cylinder alarm points:", ["100 and 600 PSI", "700 and 145 PSI", "200 and 1200 PSI", "none of the above"], 'B'),
 q("Only approved 9 volt DC alkaline batteries may be used in the Monitron/Sentinel?", TF, 'A'),
 q("The drain valve must not open at 10 mbar of breathing loop pressure?", TF, 'A'),
 q("A major component group of the BG4 is the:", ["transducer", "minimum valve", "breathing loop", "dosage line"], 'C'),
 q("The first cylinder pressure warning for the BG4?", ["1500 PSI", "2600 PSI", "Approximately 25% of full cylinder", "± 10 percent of full cylinder pressure"], 'C'),
 q("What variables would affect the duration of the BG4 use?", ["User's physical condition", "Stress, anxiety and excitement", "Amount of physical work performed", "All of the above apply"], 'D'),
 q("The relief valve vents exhaled air from the input of the CO2 scrubber.", TF, 'A'),
 q("Both dosage and positive pressure leak tests must be timed for 1 minute?", TF, 'B'),
 q("The mask must always be leak tested after replacing the lens?", TF, 'A'),
 q("The Monitron/Sentinel System consists of how many components?", ["One", "Two", "Three", "None of the above"], 'C'),
 q("What is purpose of the sintered filter?", ["Water filter", "Filters the dosage O2", "Vents excess pressure", "Filters ambient air pressure (zero reference)"], 'C'),
 q("The carbon composite or metal cylinder must be hydro-tested every:", ["3 years", "4 years", "5 years", "15 years"], 'C'),
 q("An alarm warning the user that the oxygen cylinder has not been turned on?",
   ["Low battery indicator", "Low-pressure leak test", "Low-pressure warning that activates at 700 PSI when breathing", "Low-pressure warning that activates before 1.4 mbar within the breathing loop"], 'D'),
 q("Color, odor, and taste are physical properties that can help you identify a gas, especially during ___ exploration.", ["Emergency", "Surface", "Barefaced", "None of the above"], 'C'),
 q("You can tolerate concentrations of up to 1/2 of 1 percent CO2 over a 10-hour daily period without harmful effects.", TF, 'B'),
 q("The specific gravity of Carbon Dioxide is:", ["1.2591", "1.9125", "1.5219", "1.5291"], 'D'),
 q("After a fire, explosion, or flood in a mine, rescue teams are usually needed to go into the mine to assess and reestablish working conditions.", TF, 'B'),
 q("When it comes to fixing the ventilation, the fresh air base will be counting on you to build controls where and how you are instructed.", TF, 'B'),
 q("With mechanical ventilation, mine fans are used to create the pressure differential by changing the air pressure at specific points in the mine.", TF, 'A'),
 q("A blast door is designed to open and relieve pressure when there is blasting so that a bulkhead will not be blown out.", TF, 'A'),
 q("Per 30 CFR Part 49, all mine rescue team members must have completed physical examinations in the past ___ months preceding the contest and are capable of performing strenuous work under oxygen.", ["6", "12", "24", "None of the above"], 'B'),
 q("For purposes of contest work, no barricade will be breached if Hydrogen sulfide exceeds (0.001%).", TF, 'B'),
 # q4 and q6 depend on a diagram — now included with the image.
 qi("What is the component circled on the reducer (shown)?", ["Relief valve", "Transducer", "Dosage line", "Minimum valve"], 'B', '2014_sw_drager_reducer'),
 qi("The valve shown should open/activate between what ranges?", ["0.1 to 2.5 mbar", "1.0 to 3.0 mbar", "2.0 to 5.0 mbar", "14 mbar or greater"], 'A', '2014_sw_drager_valve'),
]

# ---- 2016 Tennessee Regional TECHNICIAN (pk1383, "BioPak Tech Team"); printed
# answer sheet on p13-14. All 30 are text MC/True-False. ----
TENN_TECH = [
 q("___ is a mixture of carbon monoxide and air which results from a mine fire.", ["Afterdamp", "Stinkdamp", "Whitedamp", "Blackdamp"], 'C'),
 q("Specific gravity of Acetylene ___", ["0.9672", "0.9677", "0.9107", "0.9117"], 'C'),
 q("A partially opened mine door can be used as a regulator", TF, 'A'),
 q("The smoke tube is used to measure medium-and high-velocity air movement and anemometer is used mainly to determine what direction very slow-moving air is moving", TF, 'B'),
 q("Temporary bulkheads built in a passageway should be placed at least 4 to 6 feet into the passageway in order that",
   ["Sufficient space is available to construct a permanent bulkhead", "It will be protected from further explosions", "It will not be affected by fire if a fire should spread to that passageway", "None of the above"], 'A'),
 q("Explosive range and flammability of Propane from", ["2.12 to 9.35 percent in normal air", "2.32 to 9.35 percent in normal air", "2.12 to 9.55 percent in normal air", "2.32 to 9.55 percent in normal air"], 'A'),
 q("Specific gravity of Carbon Dioxide", ["1.5894", "1.5299", "1.5984", "1.5291"], 'D'),
 q("The traverse method is used when", ["Erecting a temporary bulkhead", "Taking a reading with a smoke tube", "Taking a reading with an anemometer", "None of the above"], 'C'),
 q("In general, cold air displaces warm air in the mine due to the differences in elevation and in temperature of the workings", TF, 'B'),
 q("Which of the following statements is false", ["An increase in temperature makes a gas diffuse more rapidly", "A decrease in temperature slows down the rate of diffusion", "An increase in pressure slows down the rate of diffusion", "A decrease in pressure slows it down"], 'D'),
 q("Industrial Scientific recommends a minimum procedure frequency of one week for performing a bump test on an MX6 ibrid.", TF, 'B'),
 q("A bump test proves that installed sensors are measuring accurately.", TF, 'B'),
 q("A configuration menu is indicated by a yellow background on the LCD screen.", TF, 'A'),
 q("The typical T90 response time for a Hydrogen (H2) sensor is 60 seconds.", TF, 'B'),
 q("If the instrument is still reading gas while in the configuration mode, and there is an alarm, the user must manually return to the gas-monitoring screen.", TF, 'B'),
 q("Zero air must be applied to zero which type of sensor?", ["NO2", "NO", "H2S", "CO2"], 'D'),
 q("During calibration, the appropriate calibration gas should be applied at a flow rate of ___ lpm.", ["0.5", "1.0", "1.5", "2"], 'A'),
 q("Passwords are a minimum of ___ characters and a maximum of ___.", ["3, 8", "4, 10", "3, 10", "4, 8"], 'C'),
 q("On the gas-monitoring display screen, the sensor types are displayed as ___ text during normal operation, and ___ text during alarm conditions.",
   ["Solid black, blinking red", "Solid black, solid red", "Solid black, blinking black", "Blinking black, blinking red"], 'C'),
 q("What is the expected typical run time for a fully charged MX6 ibrid with an extended range Li-ion battery, without pump, and CO, O2, LEL (catalytic), and H2S sensors installed?", ["36 hrs.", "24 hrs.", "20 hrs.", "12 hrs."], 'A'),
 q("MSHA requires Periodic Maintenance should be performed at least ___ on Mine Rescue Breathing Apparatus.", ["Weekly", "Quarterly", "Every 30 days"], 'C'),
 q("Closed Circuit Breathing Apparatus Oxygen cylinders must be hydrostatically tested every ___.", ["One Year", "Three Years", "Five Years"], 'C'),
 q("In a properly working positive pressure NIOSH/MSHA approved Closed Circuit breathing apparatus the pressure inside the breathing loop/circuit is:", ["Lower than ambient", "The same as ambient", "Slightly higher than ambient"], 'C'),
 q("If a slight leak occurs in the breathing circuit or facemask seal, the user generally will:", ["Hit the demand valve more often", "Reduce duration", "All of the above"], 'C'),
 q("Turn-around Maintenance should be performed", ["As soon as possible after each use", "On a monthly basis", "During periodic maintenance"], 'A'),
 q("There are various methods to eliminate or reduce mask fogging. Which method is the least likely to work:", ["Depress the Emergency By-Pass Valve", "Use an approved wiper", "Use an approved anti-fog spray or solution"], 'A'),
 q("When completing washing/disinfection during turn-around maintenance users may use any antibacterial cleaner they choose because", ["Bleach works on any germ so I can use it", "Alcohol is used in hospitals so I can use it", "None of the above"], 'C'),
 q("My Mine Rescue Closed Circuit Breathing Apparatus uses ___ in the cylinder because:", ["Breathing Air", "Compressed Air", "Medical Grade Oxygen"], 'C'),
 q("Under extremely heavy work conditions, if the user inhales and collapses the breathing bag or diaphragm as far as it can travel, it activates the", ["By-Pass Valve", "Demand Valve", "Relief Valve"], 'B'),
 q("If either or both the constant add or the demand valve fails in your apparatus, the user can still manually fill the breathing chamber by activating the", ["Emergency By-Pass Valve", "Demand/Minimum Valve", "Relief Valve"], 'A'),
]

# ---- 2014 Ohio Valley PRESHIFT (pk917): statement-of-fact test, unlabeled
# word-group choices; correct choice matched to the highlighted answer section at
# the back of the file. Transcribed fully (the auto sof-highlight handler dropped
# questions whose answer word appears in more than one choice). ----
OV_PRESHIFT = [
 q("Each underground coal mine operator shall ensure that at least 2 miners in each working section on each production shift are proficient in the use of all fire ___ equipment available on such working section, and know the location of such fire ___ equipment.", ["retardant, suppression", "combative, fighting", "suppression, suppression"], 'C'),
 q("The end of permanent roof support shall be posted with a readily ___ ___, or a physical barrier shall be installed to impede travel beyond permanent support.", ["audible, warning", "visual, warning", "reflective, devise"], 'B'),
 q("Roof support materials, sequence of roof support installation and spacing, are stated in the ___ Roof Control Plan.", ["Initial", "Written", "Approved"], 'C'),
 q("Test holes, spaced at intervals specified in the roof control plan, shall be drilled to a depth at least ___ inches ___ the anchorage horizon of mechanically anchored tensioned roof bolts being used.", ["18, below", "12, above", "24, higher"], 'B'),
 q("Chemical extinguishers shall be examined every ___ ___ and the date of the examination shall be written on a permanent tag attached to the extinguisher.", ["12, months", "24, months", "6, months"], 'C'),
 q("Any area of the mine where a hazardous condition is observed shall be posted with a ___ danger sign where anyone entering the area would pass.", ["visible", "conspicuous", "reflective"], 'B'),
 q("A visual examination of the roof, face and ribs shall be made immediately before any work is started in an area and thereafter as conditions ___.", ["warrant", "found", "examined"], 'A'),
 q("The last open crosscut is the crosscut in the line of pillars containing the permanent stoppings that ___ the ___ air courses and the return air courses.", ["isolate, intake", "prevent, intake", "separate, intake"], 'C'),
 q("The mine ventilation map shall show the direction of ___ ___ in all underground areas of the mine.", ["air, movement", "air, course", "air, flow"], 'C'),
 q("Power wires and ___, except trolley wires and trolley feeder wires, and bare signal wires shall be insulated ___ and fully protected.", ["Cables, properly", "cables, adequately", "feeds, entirely"], 'B'),
]

# ---- 2014 Ohio Valley BENCH (pk913): Bio-Pak 240R statement-of-fact test.
# q1-20 are the multiple-choice statements (p0-1); q21-30 are a diagram-based
# parts-ID section (skipped). Answers from the highlighted answer section (p6-7).
# The SAME test is filed as the 2015 NMRA Post 6 BioPak test (pk1145). ----
OV_BENCH = [
 q("Oxygen will ___ cause materials to ___ without the presence of an ignition source.", ["always, ignite", "not, ignite", "sometimes, burn"], 'B'),
 q("The BioPak 240 Revolution is approved when the oxygen cylinder is fully charged with compressed ___ or aviation grade oxygen at ___ psi.", ["construction, 3010", "medical, 2660", "medical, 3000"], 'C'),
 q("Always ___ for a current ___ test date.", ["look, manufacturers", "check, hydrostatic", "check, manufacturers"], 'B'),
 q("Replace the battery when the low battery alarm has activated, after ___ ___ of use or every 6 months whichever comes first.", ["100, hours", "200, days", "200, hours"], 'C'),
 q("The usual scrubber consists of ___ and a ___ core. Do not reuse previously used CO2 absorbent cartridges or the rubber gaskets.", ["pumice, paper", "limestone, paper", "limestone, plastic"], 'C'),
 q("Allow all components to remain ___ by the cleaning solution a minimum of 10 minutes.", ["wetted", "moist", "soaked"], 'A'),
 q("Apply anti-fog solution or ___ to both halves of the ___ before every use to ensure mask lens do not scratch.", ["water, felt", "water, chamois", "soap, chamois"], 'B'),
 q("Do not expose opened CO2 scrubber cartridges to ___ air for more than 20 minutes.", ["outside", "dry", "ambient"], 'C'),
 q("Install each CO2 canister into the SCBA so that the ___ end cap is ___ on the top side of the canister.", ["red, looking", "blue, visible", "red, visible"], 'C'),
 q("A low battery alarm is indicated by a Red, Green, Blue light sequence followed by a ___ alarm ___ any time the battery will not complete a four-hour mission.", ["momentary, beep", "short, beep", "short, chirp"], 'C'),
 q("If a quick Turn-Around ___ has been performed, the SCBA will function and is designed to work wet.", ["Cleaning", "Maintenance", "Testing"], 'B'),
 q("The RMS will automatically ___ ___ once the system pressure has dropped below 25 psig.", ["power, down", "turn, off", "power, up"], 'A'),
 q("___-___ and Dow-111 are the only o-ring lubricants that shall be utilized on the SCBA components.", ["Cristo-Grease", "Silicone-Lube", "Cristo-Lube"], 'C'),
 q("___ Use Dow 111 on any o-ring seal that comes in contact with high-pressure oxygen.", ["ALWAYS", "NEVER", "SOMETIMES"], 'B'),
 q("High breathing ___ during ___ could be caused by the facepiece exhalation valve sticking closed.", ["rates, inhalation", "rates, exhalation", "resistance, exhalation"], 'C'),
 q("High breathing resistance during inhalation could be caused by the facepiece ___ check valve sticking closed.", ["inhalation", "exhalation", "breathing"], 'A'),
 q("High breathing ___ during ___ could be caused by the demand valve in breathing chamber has failed.", ["resistance, exhalation", "resistance, inhalation", "rates, breathing"], 'B'),
 q("BioPak weight, ready to use is 34 pounds.", ["43", "34", "36"], 'B'),
 q("BioPak Carbon Dioxide Scrubber is Dual, single use ___ ___ cartridges, non-dusting, non-channeling, non-hazardous.", ["Limestone Pellets", "Calcium Hydroxide", "Calcium Pellets"], 'B'),
 q("The CO2 Scrubber should be replaced after ___ use.", ["every", "multiple", "1"], 'C'),
]

# pk913 parts-ID section (q21-30): each "Identify part #N" shows its assembly
# diagram; answers from the highlighted parts answer section (p9-12).
_LH = '2014_ohiovalley_bench_lower_housing'
_PN = '2014_ohiovalley_bench_pneumatic'
_CS = '2014_ohiovalley_bench_center_section'
_FM = '2014_ohiovalley_bench_facemask'
OV_BENCH_PARTS = [
 qi("Lower Housing Assembly — identify part #1.", ["Upper Housing Shell", "Lower Housing Shell", "Lower Case Shell"], 'B', _LH),
 qi("Lower Housing Assembly — identify part #7.", ["Shell Spacer", "Aluminum Spacer", "Vent Spacer"], 'C', _LH),
 qi("Lower Housing Assembly — identify part #12.", ["Shell Foam Spacer", "Latch Foam Pad", "Moisture Pads"], 'B', _LH),
 qi("Pneumatic Assembly — identify part #1.", ["Bypass Supply Line", "Bypass Feed Tube", "Bypass Oxygen Line"], 'B', _PN),
 qi("Pneumatic Assembly — identify part #3.", ["Oxygen Feed Tube", "Oxygen Feed Line", "Oxygen Feed Branch"], 'A', _PN),
 qi("Pneumatic Assembly — identify part #9.", ["Oxygen Regulator Gage", "Air Regulator Monitor", "Oxygen Regulator Assembly"], 'C', _PN),
 qi("Center Section Assembly — identify part #2.", ["Oxygen Supply Line", "Demand Feed Tube", "Oxygen Feed Tube"], 'B', _CS),
 qi("Center Section Assembly — identify part #9.", ["Demand Add Line", "Demand Add Fitting", "Demand Add Fixture"], 'B', _CS),
 qi("Center Section Assembly — identify part #14.", ["Breathing Diaphragm", "Flexible Shell", "Flexible Diaphragm"], 'C', _CS),
 qi("AV3500 Facemask (Complete) — identify part #9.", ["AV 3500 Facepiece Adapter", "AV 3500 Facepiece Connector", "AV 3500 Hose Adapter"], 'C', _FM),
]

# ---- 2015 NMRA Post 6 BioPak (pk1145): same Bio-Pak 240R statement-of-fact test
# template as the 2014 Bench, but q2/q14/q18/q20 differ. q1-20 MC (answers from
# its own highlighted answer section p6-7); q21-30 parts section is identical to
# the Bench test, so it reuses OV_BENCH_PARTS (same diagrams). ----
BIOPAK_2015 = [
 q("Oxygen will ___ cause materials to ___ without the presence of an ignition source.", ["always, ignite", "not, ignite", "sometimes, burn"], 'B'),
 q("A ___ gas may cause cylinder corrosion.", ["Inert", "explosive", "foreign"], 'C'),
 q("Always ___ for a current ___ test date.", ["look, manufacturers", "check, hydrostatic", "check, manufacturers"], 'B'),
 q("Replace the battery when the low battery alarm has activated, after ___ ___ of use or every 6 months whichever comes first.", ["100, hours", "200, days", "200, hours"], 'C'),
 q("The usual scrubber consists of ___ and a ___ core. Do not reuse previously used CO2 absorbent cartridges or the rubber gaskets.", ["pumice, paper", "limestone, paper", "limestone, plastic"], 'C'),
 q("Allow all components to remain ___ by the cleaning solution a minimum of 10 minutes.", ["wetted", "moist", "soaked"], 'A'),
 q("Apply anti-fog solution or ___ to both halves of the ___ before every use to ensure mask lens do not scratch.", ["water, felt", "water, chamois", "soap, chamois"], 'B'),
 q("Do not expose opened CO2 scrubber cartridges to ___ air for more than 20 minutes.", ["outside", "dry", "ambient"], 'C'),
 q("Install each CO2 canister into the SCBA so that the ___ end cap is ___ on the top side of the canister.", ["red, looking", "blue, visible", "red, visible"], 'C'),
 q("A low battery alarm is indicated by a Red, Green, Blue light sequence followed by a ___ alarm ___ any time the battery will not complete a four-hour mission.", ["momentary, beep", "short, beep", "short, chirp"], 'C'),
 q("If a quick Turn-Around ___ has been performed, the SCBA will function and is designed to work wet.", ["Cleaning", "Maintenance", "Testing"], 'B'),
 q("The RMS will automatically ___ ___ once the system pressure has dropped below 25 psig.", ["power, down", "turn, off", "power, up"], 'A'),
 q("___-___ and Dow-111 are the only o-ring lubricants that shall be utilized on the SCBA components.", ["Cristo-Grease", "Silicone-Lube", "Cristo-Lube"], 'C'),
 q("There are ___ user serviceable components on the oxygen cylinder assembly.", ["two", "no", "one"], 'B'),
 q("High breathing ___ during ___ could be caused by the facepiece exhalation valve sticking closed.", ["rates, inhalation", "rates, exhalation", "resistance, exhalation"], 'C'),
 q("High breathing resistance during inhalation could be caused by the facepiece ___ check valve sticking closed.", ["inhalation", "exhalation", "breathing"], 'A'),
 q("High breathing ___ during ___ could be caused by the demand valve in breathing chamber has failed.", ["resistance, exhalation", "resistance, inhalation", "rates, breathing"], 'B'),
 q("BioPak weight, ready to use is ___ pounds.", ["43", "34", "36"], 'B'),
 q("BioPak Carbon Dioxide Scrubber is Dual, single use ___ ___ cartridges, non-dusting, non-channeling, non-hazardous.", ["Limestone Pellets", "Calcium Hydroxide", "Calcium Pellets"], 'B'),
 q("The CO2 Scrubber should be replaced after ___ use.", ["every", "one", "1"], 'C'),
]

# 2013 Ohio Valley BG-4 (pk1793) parts-ID section (q21-27, q30; the source PDF is
# missing the q28/q29 pages). Answers from its own key page (p7). Imported and
# appended to the BG-4 quiz by build_manual.py.
BG4_PARTS = [
 qi("BG-4 — identify item No. 10.", ["Switch Box", "Sensor Box", "Distribution Box"], 'A', '2013_bg4_overview'),
 qi("BG-4 — identify item No. 11.", ["Sensor Reducer Unit", "Pressure Unit", "Sensor Unit"], 'C', '2013_bg4_overview'),
 qi("BG-4 — identify item No. 21.", ["Distribution Hose", "Oxygen Supplement Hose", "Dosage Hose"], 'A', '2013_bg4_overview'),
 qi("Breathing Hose Assembly — identify item No. 2.", ["Exhalation Valve Seat", "Inhalation Valve Seat", "Exhalation Valve Housing"], 'B', '2013_bg4_hose'),
 qi("Breathing Hose Assembly — identify item No. 3.", ["Exhalation Valve Seat", "Inhalation Valve Seat", "Exhalation Valve Housing"], 'A', '2013_bg4_hose'),
 qi("Breathing Hose Assembly — identify item No. 8.", ["Facepiece Connector O'Ring", "Coupler Sealing Ring", "Toroidal Sealing Ring"], 'C', '2013_bg4_hose'),
 qi("Sentinel — identify item No. 7.", ["Pressure Sending Unit", "Pressure Sensor", "Pressure Reducer Sensor"], 'B', '2013_bg4_sentinel'),
 qi("Oxygen Cylinder — identify item No. 20.", ["Bursting Disc", "Safety Disc", "Safety Cap"], 'A', '2013_bg4_cylinder'),
]

# 2013 Ohio Valley BioPak 240-R (pk1794) parts-ID section q21-30 (one assembly
# diagram per page, p3-12). Answers from its own key page (p13). Appended to the
# BioPak quiz by build_manual.py.
_BP = '2013_biopak_'
BIOPAK_PARTS = [
 qi("BioPak 240 Revolution Complete — identify item No. 4.", ["Back Cover Assembly", "Back Housing Assembly", "Upper Housing Assembly"], 'C', _BP + 'complete'),
 qi("Lower Housing Assembly — identify item No. 3.", ["External Oxygen Knob", "Outer Oxygen Knob", "External Cylinder Knob"], 'A', _BP + 'lower_housing'),
 qi("Pneumatic Assembly — identify item No. 11.", ["Remote Cylinder Gauge", "External Gauge Assembly", "Remote Gauge Assembly"], 'C', _BP + 'pneumatic'),
 qi("Manifold Assembly — identify item No. 2.", ["Constant Add Flow Adjustor Assembly", "Constant Add Flow Restrictor Assembly", "High Pressure Flow Restrictor Assembly"], 'B', _BP + 'manifold'),
 qi("Center Section Assembly — identify item No. 14.", ["External Diaphragm", "Diaphragm Disc", "Flexible Diaphragm"], 'C', _BP + 'center_section'),
 qi("Facepiece Assembly — identify item No. 3.", ["Breathing Hose Adapter", "Facepiece Connector Assembly", "Facepiece Adaptor Assembly"], 'C', _BP + 'facepiece'),
 qi("Center Section Lid Assembly — identify item No. 3.", ["Flow Restrictor", "Flow Baffle", "Flow Plate"], 'B', _BP + 'lid'),
 qi("Diaphragm Assembly — identify item No. 2.", ["Vent Release", "Vent Valve", "Vent Cap"], 'C', _BP + 'diaphragm'),
 qi("Tool Kit — identify item No. 4.", ["Test Key", "Test Spacers", "Tests Plugs"], 'A', _BP + 'toolkit'),
 qi("Ice Canister Freeze Form — identify item No. 2.", ["Freeze Tube", "Ice Tube", "Ice Canister"], 'A', _BP + 'ice_canister'),
]

# 2013 NMRA Post 2 Kentucky BG4 (pk1792) parts-ID section q21-30: three assembly
# diagrams (p4-6) whose designation tables have fill-in-the-blank part names.
# Answers from its own key page (p13). Appended to the Kentucky quiz.
_KY = '2013_kentucky_'
KENT_PARTS = [
 qi("Cooling Canister — item 2 is the “___ for Cooler”. Which word completes it?", ["Lid", "Cover", "Top"], 'B', _KY + 'cooling_canister'),
 qi("Cooling Canister — item 4 is the “Angle ___”. Which word completes it?", ["Connector", "Connection", "Line"], 'A', _KY + 'cooling_canister'),
 qi("Cooling Canister — item 5 is the “___ Ring”. Which word completes it?", ["Reactor", "Reacting", "Reaction"], 'C', _KY + 'cooling_canister'),
 qi("Refillable Cartridge — item 1 is the “Refillable ___”. Which word completes it?", ["Canister", "Container", "Cartridge"], 'C', _KY + 'refillable_cartridge'),
 qi("Refillable Cartridge — item 5 is the “___ Scrubber Screen”. Which word completes it?", ["Refillable", "Reusable", "Regenerative"], 'A', _KY + 'refillable_cartridge'),
 qi("Refillable Cartridge — item 6 is the “___ Mats”. Which word completes it?", ["Filter", "Replaceable", "Filler"], 'A', _KY + 'refillable_cartridge'),
 qi("Drain/Relief/Minimum Valve Assembly — item 2 is the “___ Case”. Which word completes it?", ["Crater", "Valve", "Clamp"], 'A', _KY + 'drain_valve'),
 qi("Drain/Relief/Minimum Valve Assembly — identify item 9.", ["Coupler", "Coupling", "Connecting"], 'B', _KY + 'drain_valve'),
 qi("Drain/Relief/Minimum Valve Assembly — item 18 is the “Valve ___”. Which word completes it?", ["Disc", "Seat", "Plate"], 'C', _KY + 'drain_valve'),
 qi("Drain/Relief/Minimum Valve Assembly — item 23 is the “Angle ___”. Which word completes it?", ["Connector", "Coupling", "Valve"], 'A', _KY + 'drain_valve'),
]

# ---- 2019 NMRA Post 6 Statement-of-Fact test (pk1652): one PDF holds two tests
# (Day 1 p0-1, Day 2 p2-3), each numbered 1-10 with a word answer key — the number
# restart defeats the auto extractor, so both days are transcribed into one 20-Q
# quiz. Correct choice matched to each day's printed word key. ----
NMRA2019 = [
 q("Day 1 - ___ method of indirect firefighting is flooding the sealed fire area with water.", ["Common", "Every", "One"], 'C'),
 q("Day 1 - Once an explosion has occurred, there is ___ the possibility of further explosions.", ["sometimes", "generally", "always"], 'C'),
 q("Day 1 - Mine rescue teams may find it necessary to use line brattice to sweep noxious or explosive gases from a ___ area.", ["every", "face", "barricade"], 'B'),
 q("Day 1 - Once ventilation has been re-established and fresh air advanced, non-___ crews can take over the rehabilitation and cleanup effort.", ["rescue", "apparatus", "essential"], 'B'),
 q("Day 1 - Rescue teams are responsible for assessing ___ to the ventilation system.", ["damage", "effectiveness", "needs"], 'A'),
 q("Day 1 - Information the team relays to the fresh-air base as it ___ is known as the 'progress report'.", ["advances", "progresses", "proceeds"], 'C'),
 q("Day 1 - It is the responsibility of rescue team ___ to have all the information needed to do the work.", ["captain", "personnel", "members"], 'C'),
 q("Day 1 - When a team locates a body, its location and position should be marked on a ___ and on the roof or rib close to the body.", ["team map", "mine map", "B/O map"], 'B'),
 q("Day 1 - The rescue team captain should regulate the team's pace according to conditions ___.", ["encountered", "found", "discovered"], 'A'),
 q("Day 1 - When a body is first located, every effort should be made not to disturb any possible ___ in the area.", ["conditions", "information", "evidence"], 'C'),
 q("Day 2 - Low expansion foam is very ___ and heavy and can only be used when you're close enough to a fire to force the foam directly onto the fire.", ["hard", "dry", "wet"], 'C'),
 q("Day 2 - ___ is explosive.", ["Carbon Dioxide", "Carbon monoxide", "Sulphur dioxide"], 'B'),
 q("Day 2 - Oxygen is a supporter of ___.", ["fire", "dissolution", "combustion"], 'C'),
 q("Day 2 - If smoke is so ___ as to make visibility poor, you may need to keep in constant physical contact with an object or a rib in order to feel your way along.", ["thick", "dense", "light"], 'B'),
 q("Day 2 - Two types of fire ___ be fought directly, fuel rich and spontaneous combustion.", ["shouldn't", "cannot", "shall"], 'B'),
 q("Day 2 - Team safety must not be ___.", ["ignored", "compromised", "forgotten"], 'B'),
 q("Day 2 - Monitoring ___ and gases helps determine the effectiveness of firefighting and the potential danger of an explosion.", ["pressures", "readings", "reports"], 'A'),
 q("Day 2 - Sulfur dioxide and hydrogen sulfide are water ___ gases.", ["filled", "containing", "soluble"], 'C'),
 q("Day 2 - Color, odor, and taste are physical ___ that help to identify gases during barefaced exploration.", ["conditions", "feelings", "properties"], 'C'),
 q("Day 2 - Only detectors and chemical analysis can ___ identify a gas.", ["Always", "positively", "constantly"], 'B'),
]

# ---- 2021 Southwest Wyoming Mutual Aid DAY 2 (pk295): a multi-answer test
# ("circle the letter/s; there may be more than one correct answer"), key pk148.
# Only A/B/C options, so the four multi-answer items (key "A,B,&C" / "A&C") are
# adapted to single-select by adding an "All of the above" / "Both A and C" choice.
SWWMA_DAY2 = [
 q("Atmospheric pressure and temperature are important factors because they:", ["Affect the rate of diffusion of a gas by ventilation.", "Can cause false readings on gas detection instruments.", "Lower oxygen content in the mine."], 'A'),
 q("Two gases that are highly soluble in water are:", ["Hydrogen sulfide and hydrogen", "Nitrogen and sulfur dioxide", "Hydrogen sulfide and sulfur dioxide"], 'C'),
 q("The explosive range of methane/air mixture (normally 5-15%) will change if:", ["Certain other combustible gases are present.", "Coal dust is suspended in the atmosphere.", "There is less than 12.1% oxygen in the atmosphere.", "All of the above"], 'D'),
 q("Which of the following is not true of sulfur dioxide?", ["It is explosive.", "It is toxic.", "It can occur during mine fires."], 'A'),
 q("A gas that is normally found near the roof or in high places in the mine, is said to have a low:", ["Level of toxicity.", "Level of solubility", "Specific gravity"], 'C'),
 q("A smoke tube is a devise used to:", ["Determine oxygen content of the mine atmosphere.", "Determine direction and velocity of air flow.", "Detect leaks in temporary stoppings."], 'B'),
 q("Mine rescue teams erecting temporary stoppings/bulkheads in atmosphere with elevated methane readings should:", ["Use only inflatable seals.", "Mine rescue teams should never enter such atmosphere.", "Use non-sparking tools, nails, and spads."], 'C'),
 q("Barefaced exploration should be attempted only when:", ["No breathing apparatus is available.", "Miners are trapped in the mine.", "A backup mine rescue team with apparatus is immediately available."], 'C'),
 q("Gas readings should be taken:", ["At all intersections.", "At any dead end or face area.", "At the furthest point of travel in any entry or heading.", "All of the above"], 'D'),
 q("Debriefings are held to:", ["Inform news reporters of developments.", "Inform family members of developments.", "Review the rescue team's findings after they have returned from underground."], 'C'),
 q("Class A fires are those that involve:", ["Ordinary combustible materials such as wood, plastics, paper, and cloth.", "Combustible cooking media such as oils and grease commonly found in commercial kitchens.", "Flammable or combustible liquids such as gasoline, diesel, kerosene, and grease."], 'A'),
 q("A monoammonium phosphate extinguisher is effective in fighting:", ["Class A fires", "Class B Fires", "Class C Fires", "All of the above"], 'D'),
 q("Which one of the following actions is not a suggested procedure when a team locates a body?", ["Outline the body with chalk or paint on the floor.", "Clean up the area around the body for safety and ease of recovery.", "Report the location to the command center."], 'B'),
 q("A mine rescue team could remove standing water from an unventilated area.", ["If gas conditions permit, using non-conductive suction line and a pump set up in fresh air.", "Standing water can not be pumped from an unventilated area.", "If the line loses suction, toxic or explosive gases from the contaminated atmosphere could not be drawn out.", "Both A and C"], 'D'),
 q("Probably the best material to use for sealing a mine fire is:", ["Brattice cloth", "Cement blocks", "Tongue-and-groove lumber"], 'B'),
]

# ---- 2022 Virginia Governor's Cup (pk174): statement-of-fact test, unlabeled
# word-group choices; answer doc pk175 marks the correct choice in RED text. ----
GOV_CUP = [
 q("Clean, dry air at sea level is made up of ___ nitrogen and 21 percent oxygen.", ["58 percent", "68 percent", "78 percent"], 'C'),
 q("A smoke tube is used to show the direction and ___ of slow moving air.", ["quantity", "velocity", "speed"], 'B'),
 q("High volatile coal burns ___ than low or medium volatile coal.", ["much hotter", "much faster", "more readily"], 'B'),
 q("When looking for survivors, it is important to ___ and listen for clues.", ["both look", "look carefully", "look around"], 'A'),
 q("When survivors are ___, their location, identities, and condition should be reported immediately to the command center.", ["rescued", "found", "located"], 'C'),
 q("Oxygen is a supporter of ___.", ["life", "explosions", "combustion"], 'C'),
 q("Teams should report the lowest team member's oxygen ___ reading at each team check.", ["bottle", "psi", "gauge"], 'C'),
 q("Mines below the water table tend to have ___ methane than those above the water table.", ["less", "more", "lighter"], 'B'),
 q("To test for methane, use a methane detector or ___.", ["bottle sampling", "chemical analysis", "safety lamp"], 'B'),
 q("As the team advances, the map man records what the ___ by marking the information on a mine map.", ["team encounters", "others find", "team locates"], 'A'),
]

# ---- 2023 West Virginia State Interagency DAY 1 (pk304, scanned test); its
# answer doc pk306 is a text copy with the correct choice yellow-highlighted. ----
WV_DAY1 = [
 q("When ___ a mine fire, you should be careful to ensure that there are no abrupt changes in the ventilation over the fire area.", ["Extinguishing", "Sealing", "Fighting"], 'B'),
 q("___ sampling-pipes are inserted in temporary and permanent seals for the purpose of collecting air samples from the sealed area.", ["Non-Metallic", "Non-sparking", "Non-Explosive"], 'A'),
 q("Before going underground to ___ for a fire or to fight a fire, the team should know about any possible ignition sources that may exist in the affected area.", ["Explore", "Look", "Prepare"], 'A'),
 q("The specific gravity of ___ is 1.5291.", ["Carbon Monoxide", "Sulfur Dioxide", "Carbon Dioxide"], 'C'),
 q("___ is a mixture of carbon dioxide, nitrogen and air which is oxygen deficient.", ["White damp", "After damp", "Black damp"], 'C'),
 q("Breathing air containing 10 percent ___ causes violent panting and can lead to death.", ["Nitrogen dioxide", "Carbon dioxide", "Hydrogen sulfide"], 'B'),
 q("___ should be allowed for a fire area to cool before it is unsealed.", ["Amble time", "Sufficient time", "Recommended time"], 'B'),
 q("___ should be marked to warn other teams that may enter the area after yours.", ["Dangerous areas", "Unsafe areas", "Hazardous areas"], 'C'),
 q("All ___ should be well hitched in the floor, roof, and ribs to improve their strength.", ["Permanent seals", "Block seals", "Temporary seals"], 'C'),
 q("The main objectives of exploration work during a mine fire are locating the fire and ___ conditions in the fire area.", ["Evaluating", "Observation", "Assessing"], 'C'),
]

# ---- 2023 Missouri Regional Drager BG-4 (pk372, scanned); clean printed key
# pk373. q1-6 MC; q11-20 parts (Sentinel p1, Oxygen Cylinder p2). The q7-10 pages
# are missing from the source PDF (key lists them but no question pages). ----
_MD = '2023_missouri_drager_'
MO_DRAGER = [
 q("A ___ exhalation or inhalation valve could be caused by a defective valve seat or valve disc.", ["Malfunctioning", "Leaky", "Defective"], 'B'),
 q("A ___ pressure in the breathing circuit prevents ambient air from entering the system.", ["Constant", "Residual", "Positive"], 'C'),
 q("The BG-4 constant dosage must be ___ L/min.", ["1.5 to 1.8", "1.5 to 1.9", "1.4 to 1.6"], 'B'),
 q("A fully filled steel oxygen cylinder holds ___ liters of medical oxygen.", ["440", "500", "400"], 'A'),
 q("Never replace the ___ in potentially explosive areas.", ["Sentinel", "Display", "Battery"], 'C'),
 q("Insert speech diaphragm, install ___ ring and tighten with spanner.", ["Retainer", "Tightening", "Torque"], 'A'),
 qi("Sentinel — item 1.", ["Sentinel", "Controller", "Display"], 'A', _MD + 'sentinel'),
 qi("Sentinel — item 3 is the 'Angle ___'.", ["Coupling", "Connector", "Fitting"], 'B', _MD + 'sentinel'),
 qi("Sentinel — item 7 is the 'Pressure ___'.", ["Sensor", "Switch", "Controller"], 'A', _MD + 'sentinel'),
 qi("Sentinel — item 8 is the 'Copper ___'.", ["Spacer", "Washer", "Ring"], 'C', _MD + 'sentinel'),
 qi("Sentinel — item 13 is the '___ Key'.", ["Sensor", "Talley", "Switch"], 'B', _MD + 'sentinel'),
 qi("Oxygen Cylinder — item 13 is the '___ Ring'.", ["Safety", "Sealing", "O"], 'A', _MD + 'cylinder'),
 qi("Oxygen Cylinder — item 16 is the '___ Ring'.", ["Safety", "Sealing", "O"], 'B', _MD + 'cylinder'),
 qi("Oxygen Cylinder — item 18.", ["O-Ring", "Lock Washer", "Gasket"], 'B', _MD + 'cylinder'),
 qi("Oxygen Cylinder — item 20 is the 'Bursting ___'.", ["Valve", "Cap", "Disc"], 'C', _MD + 'cylinder'),
 qi("Oxygen Cylinder — item 21 is the 'Oxygen ___'.", ["Cylinder", "Canister", "Tank"], 'A', _MD + 'cylinder'),
]

# ---- 2024 Harlan County Safety Days FIRST AID test (pk488); hand-circled answers
# on the scanned pages. 15 questions. ----
HARLAN_FA = [
 q("Signs of opioid overdose include slow, shallow or no breathing, choking, or gurgling sounds, drowsiness or loss or consciousness, ___, constricted pupils, blue skin, lips, or nails.", ["large", "dark", "small"], 'C'),
 q("___ the throat with the thumb and fingers, making the universal choking sign indicates the need for help when a victim is choking.", ["Holding", "Grabbing", "Clutching"], 'B'),
 q("A wound where the top layer of skin have been ___ off, commonly seen in falls, can be best described as an abrasion.", ["scraped", "peeled", "torn"], 'A'),
 q("The ___ are found in an area behind the abdominal wall.", ["liver", "spleen", "kidneys"], 'C'),
 q("Hepa mask would be the most important type of PPE to use when caring for a patient with ___.", ["hepatitis", "tuberculosis", "herpes"], 'B'),
 q("Proper body mechanics are best defined as properly using your body to ___ a lift or move.", ["coordinate", "conduct", "facilitate"], 'C'),
 q("Carotid and ___ are the two pulse points that are referred to central pulse points.", ["branchial", "temporal", "femoral"], 'C'),
 q("Your patient has been in respiratory distress for approximately ___ minutes, your assessment reveals pale skin and cyanosis of the lips, these are signs of hypoxia.", ["30", "20", "15"], 'A'),
 q("Blood spurts from the wound, the color of the blood is bright red, and blood loss is often profuse in a short period of time are typical characteristics of ___ bleeding.", ["life threatening", "serious", "arterial"], 'C'),
 q("You are caring for a patient with an open chest wound and have covered the wound with an occlusive dressing, the patient becomes increasingly short of breath, you should partially remove the dressing to ___ air to escape.", ["allow", "prevent", "assist"], 'A'),
 q("A rate of 100 to 120 compressions per minute and a depth of at least 2 inches are the rate and depth for chest compressions on an ___.", ["patient", "mannequin", "adult"], 'C'),
 q("Opioids are medications used primarily for pain relief, common examples are ___, morphine, and fentanyl.", ["oxycodone", "hydrocodone", "methadone"], 'B'),
 q("Shock is a life-threatening condition that occurs when the circulatory system can't ___ adequate blood flow.", ["regulate", "maintain", "control"], 'B'),
 q("Head-tilt-chin lift is a maneuver used to open a victim's airway before ___ rescue breaths during CPR.", ["providing", "delivering", "performing"], 'A'),
 q("Early ___ of foreign-body airway obstruction is the key to successful outcome.", ["recognition", "detection", "consideration"], 'A'),
]

# ---- 2024 Fallen Heroes FIRST AID written exam (pk495); hand-circled answers on
# the scanned pages. 15 questions. ----
FALLEN_HEROES_FA = [
 q("___ mask would be the most important type of PPE to use when caring for a patient with tuberculosis.", ["Hepa", "Bag", "Pocket"], 'A'),
 q("The abdominal cavity contains the liver and part of the ___ intestine.", ["large", "small", "lower"], 'A'),
 q("When assessing circulation for a responsive adult patient you should assess the ___ pulse.", ["femoral", "carotid", "radial"], 'C'),
 q("Skin that is ___ in color is called cyanotic.", ["red", "bluish", "pale"], 'B'),
 q("A patient who presents with normal vital signs and shows no indications of life-threatening problems may be described as ___.", ["traumatic", "normal", "stable"], 'C'),
 q("Your patient has been in respiratory distress for approximately 30 minutes, your assessment reveals pale skin and cyanosis of the lips, these are signs of ___.", ["bronchitis", "asthma", "hypoxia"], 'C'),
 q("Protect the patient from injury and place him or her in the ___ following the seizure is an example of appropriate care for a seizure patient.", ["Recovery position", "Prone position", "Supine position"], 'A'),
 q("A wound where the top layers of skin have been scraped off, commonly seen in falls, can best be described as an ___.", ["contusion", "abrasion", "laceration"], 'B'),
 q("When the ___ is absent is a situation where it would be appropriate to place an angulated extremity back into the anatomical position.", ["Distal pulse", "Radial pulse", "Carotid pulse"], 'A'),
 q("You are caring for a patient who has one leg that is shortened with the foot rotated to one side, these are likely signs of a possible ___.", ["Dislocated femur", "Dislocated knee", "Dislocated hip"], 'C'),
 q("The most appropriate care for an open abdominal injury is to cover the wound with a ___, sterile dressing.", ["clean", "moist", "dry"], 'B'),
 q("A ratio of ___ compressions per minute and a depth of at least 2 inches are the rate and depth for chest compressions on an adult.", ["80 to 100", "100 to 120", "30 to 2"], 'B'),
 q("When more rescuers arrive on scene you should assign tasks to other rescuers and rotate compressors every ___ or more frequently if needed to avoid fatigue.", ["2-minutes", "5-minutes", "3-minutes"], 'A'),
 q("___ is an important tool for identifying whether opioids may be involved in a life-threatening emergency.", ["Patient assessment", "Initial assessment", "Scene assessment"], 'C'),
 q("___ is a life-threatening condition that occurs when the circulatory system can't maintain adequate blood flow.", ["stroke", "shock", "asthma"], 'B'),
]

# ---- 2024 Colorado Regional BIO (BioPak 240R) bench test (pk68); answer key
# pk69 marks correct choices in red. q1-10 MC; q11-20 are parts-ID on the
# Pneumatic Assembly (test p2) and Lower Housing Assembly (test p3) diagrams. ----
_CB = '2024_colorado_bio_'
COLO_BIO = [
 q("Always handle oxygen cylinders with care to ___ ___.", ["prevent accident", "prevent damage", "prevent leaks"], 'B'),
 q("The battery is to be changed in ___ air only.", ["fresh", "ambient", "zero"], 'A'),
 q("If the optional magnetic wiper is utilized soak ___ chamois surfaces of the wiper pieces with water.", ["one", "inside", "both"], 'C'),
 q("The BioPak breathing chamber has a ___ Volume greater than 6 liters.", ["Total", "Pressure", "Tidal"], 'C'),
 q("The use of an ___ will add to the workload and stress of the user.", ["240R", "BioPak", "SCBA"], 'C'),
 q("During an alarm test the LED indication should turn to a flashing red with a horn sounding when the pressure gauge reads between ___ psi.", ["550-1000", "650-1000", "750-1000"], 'B'),
 q("Claustrophobia or ___ when wearing a SCBA could limit or prevent the use of the BioPak 240 Revolution.", ["Hypertension", "Anxiety", "Anxiousness"], 'B'),
 q("The ___ gauge is protected against sudden loss of oxygen in the event of the gauge line severing by a manual disconnect located at the gauge pass through point of the housing.", ["pressure", "exterior", "oxygen"], 'A'),
 q("A foreign gas may cause cylinder ___.", ["corrosion", "deterioration", "failure"], 'A'),
 q("Cylinders that have been hydro-static tested shall be cleaned for high-pressure oxygen service per ___ ___.", ["manufacturer Standards", "Industry Standards", "national standards"], 'C'),
 qi("Pneumatic Assembly — item 3 is the '___ Feed Tube'.", ["Bypass", "Return", "Oxygen"], 'C', _CB + 'pneumatic'),
 qi("Pneumatic Assembly — item 6 is the '___ Push Button'.", ["Relief Valve", "Bypass Valve", "Minimum Valve"], 'B', _CB + 'pneumatic'),
 qi("Pneumatic Assembly — item 7 is the '___ Valve'.", ["Relief", "Bypass", "Minimum"], 'B', _CB + 'pneumatic'),
 qi("Pneumatic Assembly — item 9 is the 'Oxygen ___ Assembly'.", ["Regulator", "Distributor", "Sensor"], 'A', _CB + 'pneumatic'),
 qi("Pneumatic Assembly — item 11 is the 'Remote Gauge ___'.", ["Unit", "Display", "Assembly"], 'C', _CB + 'pneumatic'),
 qi("Lower Housing Assembly — item 2 is the '___ Springs'.", ["Air Bag", "Housing", "Diaphragm"], 'C', _CB + 'lower_housing'),
 qi("Lower Housing Assembly — item 3 is the 'External Oxygen ___'.", ["Knob", "Cap", "Adjustment"], 'A', _CB + 'lower_housing'),
 qi("Lower Housing Assembly — item 7 is the '___ Spacer'.", ["Drain", "Shell", "Vent"], 'C', _CB + 'lower_housing'),
 qi("Lower Housing Assembly — item 12 is the 'Latch ___ Pad'.", ["Rubber", "Foam", "Cushion"], 'B', _CB + 'lower_housing'),
 qi("Lower Housing Assembly — item 16 is the 'Oxygen ___ Hold-Down Strap'.", ["Cylinder", "Bottle", "Canister"], 'A', _CB + 'lower_housing'),
]

# ---- 2024 Nevada Underground (WMRA) BG4 Apparatus Bench test (pk385). Text
# layer; correct answers on the embedded Answer Key (test p5, red letters).
# q1-10 MC; q11-15 parts on the FPS 7000 Mask diagram (test p3); q16-20 parts on
# the Breathing House Assembly diagram (test p4). ----
_NB = '2024_nevada_bg4_'
NV_BG4 = [
 q("The maximum temperature of the air used to dry parts should not go above ___ degree C (___ degree F).", ["20, 68", "60, 120", "60, 140", "40, 140"], 'D'),
 q("Only oxygen (medical grade or better) with >___% purity is to be used to fill the BG-4 oxygen cylinders.", ["95.9", "21", "20", "99.5"], 'D'),
 q("___ pressure in the BG-4 is between 58 psi and 64 psi.", ["Low", "High", "Medium"], 'C'),
 q("A fully filled oxygen cylinder holds ___ ___ of medical oxygen.", ["440 mL", "220 mL", "440 L", "220 L"], 'C'),
 q("The ___ Breathing hoses use Bayonet Rings.", ["EDM", "DMP", "EMP", "EPDM"], 'D'),
 q("During the exhalation valve test, if valve is operating properly, ___ mbar is indicated on the pressure gauge.", ["+10", "+5", "-10", "-5"], 'C'),
 q("At the first low pressure warning approximately ___% of the oxygen has been used up.", ["75", "95", "99.5"], 'A'),
 q("Only the following batteries are approved for use in the Sentinel:", ["Rayovac, Eveready, Panasonic, Ultra-life Lithium", "Rayovac, Eveready, Energizer, Duracell", "Energizer, Duracell, Ultra-Life Lithium", "None of the above"], 'A'),
 q("The oxygen cylinder burst disc ruptures at ___ psi.", ["4,440", "4,450", "4,250", "4,200"], 'B'),
 q("The weight of a fully charged BG-4 apparatus is ___ kg.", ["15", "33", "58", "64"], 'A'),
 qi("FPS 7000 Mask — item 4 is the '___ Visor Frame'.", ["Lower", "Medium", "Upper"], 'A', _NB + 'fps7000_mask'),
 qi("FPS 7000 Mask — item 7.", ["Cover", "Button", "Clamp"], 'C', _NB + 'fps7000_mask'),
 qi("FPS 7000 Mask — item 9.", ["Clamp", "Cover", "Button"], 'B', _NB + 'fps7000_mask'),
 qi("FPS 7000 Mask — item 12.", ["Disc", "Button", "Clamp"], 'A', _NB + 'fps7000_mask'),
 qi("FPS 7000 Mask — item 14.", ["Disc", "Button", "Clamp"], 'B', _NB + 'fps7000_mask'),
 qi("Breathing House Assembly — item 1.", ["Tee Coupling", "Coupling", "Hose Coupling"], 'B', _NB + 'breathing_house'),
 qi("Breathing House Assembly — item 2 is the '___ Valve Seat'.", ["Inhalation", "Exhalation", "Toroidal"], 'A', _NB + 'breathing_house'),
 qi("Breathing House Assembly — item 3 is the '___ Valve Seat'.", ["Inhalation", "Exhalation", "Toroidal"], 'B', _NB + 'breathing_house'),
 qi("Breathing House Assembly — item 8 is the '___ Sealing Ring'.", ["Inhalation", "Exhalation", "Toroidal"], 'C', _NB + 'breathing_house'),
 qi("Breathing House Assembly — item 9.", ["Toroidal", "Cap", "Sealing Cap"], 'C', _NB + 'breathing_house'),
]

SCANNED = [
 {'source_pk': 385, 'title': 'BG4 Bench Written Test', 'questions': NV_BG4},
 {'source_pk': 68, 'title': 'BIO Bench Written Test', 'questions': COLO_BIO},
 {'source_pk': 488, 'title': 'First Aid Written Test', 'questions': HARLAN_FA},
 {'source_pk': 495, 'title': 'First Aid Written Test', 'questions': FALLEN_HEROES_FA},
 {'source_pk': 372, 'title': 'Drager Written Test', 'questions': MO_DRAGER},
 {'source_pk': 304, 'title': 'Day 1 Written Test', 'questions': WV_DAY1},
 {'source_pk': 174, 'title': 'Written Test', 'questions': GOV_CUP},
 {'source_pk': 295, 'title': 'Day 2 Written Test', 'questions': SWWMA_DAY2},
 {'source_pk': 1652, 'title': 'Written Test', 'questions': NMRA2019},
 {'source_pk': 1145, 'title': 'BioPak Written Test', 'questions': BIOPAK_2015 + OV_BENCH_PARTS},
 {'source_pk': 1114, 'title': 'Field Written Test', 'questions': SW_FIELD},
 {'source_pk': 1117, 'title': 'Technician Drager BG4 Written Test', 'questions': SW_BG4},
 {'source_pk': 1383, 'title': 'Technician Written Test', 'questions': TENN_TECH},
 {'source_pk': 917, 'title': 'Preshift Written Test', 'questions': OV_PRESHIFT},
 {'source_pk': 913, 'title': 'Bench Written Test', 'questions': OV_BENCH + OV_BENCH_PARTS},
]
