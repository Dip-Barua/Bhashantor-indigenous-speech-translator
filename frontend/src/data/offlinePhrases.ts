export type OfflineCategory = "Water" | "Trail & Direction" | "Help & Safety" | "Medical & Fever" | "Accommodation";

export type OfflinePhrase = {
  category: OfflineCategory;
  label: string;
  bangla: string;
  chakma: string;
  marma: string;
  english: string;
};

export const offlinePhrases: OfflinePhrase[] = [
  { category: "Water", label: "I need drinking water", bangla: "আমার পানীয় জল দরকার", chakma: "mor pani dorkar", marma: "nga yei goahmi", english: "I need drinking water" },
  { category: "Water", label: "Where can I find clean water?", bangla: "কোথায় পরিষ্কার পানি পাব?", chakma: "poriskar pani konthay pabo?", marma: "kae yei phya meng?", english: "Where can I find clean water?" },
  { category: "Water", label: "Please give me a bottle of water", bangla: "দয়া করে একটি পানির বোতল দিন", chakma: "daya kore ekkhan pani botol din", marma: "kheisai yei botol kyu", english: "Please give me a bottle of water" },
  { category: "Trail & Direction", label: "Which way is the trail?", bangla: "পথটি কোন দিকে?", chakma: "potta kon dike?", marma: "lama yainggo?", english: "Which way is the trail?" },
  { category: "Trail & Direction", label: "How far is the village?", bangla: "গ্রামটি কত দূরে?", chakma: "gramta kot dur?", marma: "village thang kare?", english: "How far is the village?" },
  { category: "Trail & Direction", label: "Is this path safe?", bangla: "এই পথটি কি নিরাপদ?", chakma: "ey pathta nirapod ki?", marma: "de lama khalang ah?", english: "Is this path safe?" },
  { category: "Help & Safety", label: "Please help me", bangla: "অনুগ্রহ করে আমাকে সাহায্য করুন", chakma: "more sahajjo din", marma: "nga go kiju lo", english: "Please help me" },
  { category: "Help & Safety", label: "I am lost", bangla: "আমি পথ হারিয়ে ফেলেছি", chakma: "mui pot harachhi", marma: "nga lama pohrei", english: "I am lost" },
  { category: "Help & Safety", label: "Please call the police", bangla: "দয়া করে পুলিশকে ডাকুন", chakma: "daya kore police ke dak din", marma: "police oh roh kheisai", english: "Please call the police" },
  { category: "Medical & Fever", label: "I have a fever", bangla: "আমার জ্বর হয়েছে", chakma: "mor jobor hoyeche", marma: "nga yemma loho", english: "I have a fever" },
  { category: "Medical & Fever", label: "I need a doctor", bangla: "আমার একজন ডাক্তার দরকার", chakma: "mor ekjon doctor dorkar", marma: "nga doctor goahmi", english: "I need a doctor" },
  { category: "Medical & Fever", label: "I feel pain here", bangla: "এখানে আমার ব্যথা করছে", chakma: "ekhanay mor betha korche", marma: "desang nga khokhoire", english: "I feel pain here" },
  { category: "Accommodation", label: "Do you have a place to stay?", bangla: "থাকার জন্য কোনো জায়গা আছে?", chakma: "thakar jonno kono jaiga ase?", marma: "thai rayo mae?", english: "Do you have a place to stay?" },
  { category: "Accommodation", label: "How much does the room cost?", bangla: "ঘরের ভাড়া কত?", chakma: "ghoror bhara kot?", marma: "room lama pya?", english: "How much does the room cost?" },
  { category: "Accommodation", label: "Please wake me at six", bangla: "দয়া করে সকাল ছটায় আমাকে উঠিয়ে দিন", chakma: "daya kore chaytay mor jagai din", marma: "kheisai nga taro ruh khorang", english: "Please wake me at six" },
];
