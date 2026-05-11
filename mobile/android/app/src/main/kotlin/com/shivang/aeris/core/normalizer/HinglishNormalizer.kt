package com.shivang.aeris.core.normalizer

/**
 * Lightweight mirror of the desktop core/normalizer.py — folds common Hinglish
 * spelling variants and number words so downstream skills see one canonical
 * form. Not exhaustive; covers the high-frequency utterances we care about.
 */
object HinglishNormalizer {

    private val romanDigits = mapOf(
        "ek" to "1", "do" to "2", "teen" to "3", "char" to "4", "chaar" to "4",
        "paanch" to "5", "panch" to "5", "che" to "6", "chhe" to "6", "chhah" to "6",
        "saat" to "7", "saath" to "7", "aath" to "8", "nau" to "9", "das" to "10",
        "gyarah" to "11", "barah" to "12", "tera" to "13", "chaudah" to "14",
        "pandrah" to "15", "solah" to "16", "satrah" to "17", "atharah" to "18",
        "unnees" to "19", "bees" to "20", "tees" to "30", "chalis" to "40",
        "pachas" to "50", "pachaas" to "50", "saath_60" to "60", "sattar" to "70",
        "assi" to "80", "nabbe" to "90", "sau" to "100", "hazar" to "1000",
        "hazaar" to "1000",
    )

    private val synonyms = mapOf(
        "kharch" to "kharch", "kharcha" to "kharch", "spent" to "kharch",
        "spend" to "kharch", "lagaye" to "kharch", "lagaya" to "kharch",
        "lagayi" to "kharch", "lagaa" to "kharch",
        "rupaye" to "rupees", "rupay" to "rupees", "rupiya" to "rupees",
        "rs" to "rupees", "inr" to "rupees", "rupee" to "rupees",
        "yaad" to "remind", "yad" to "remind", "yaadgar" to "remind",
        "dilana" to "remind", "dilao" to "remind", "dila" to "remind",
        "kar" to "do", "karo" to "do", "kardo" to "do", "kr" to "do",
        "khol" to "open", "kholo" to "open", "kholna" to "open",
        "band" to "close", "bandh" to "close", "bandkar" to "close",
        "dikha" to "show", "dikhao" to "show", "dikhayega" to "show",
        "samay" to "time", "vakt" to "time", "wakt" to "time",
        "kya" to "what", "kyaa" to "what", "kya_" to "what",
        "haath" to "hand", "hath" to "hand",
        "mahine" to "month", "mahina" to "month", "month" to "month",
    )

    fun normalize(input: String): String {
        if (input.isBlank()) return ""
        val lower = input.lowercase().trim()
            .replace(Regex("[\\u2018\\u2019\\u201C\\u201D]"), "'")
            .replace(Regex("[^a-z0-9\\u0900-\\u097F\\s.,!?'-]"), " ")
            .replace(Regex("\\s+"), " ")
        val tokens = lower.split(' ').map { tok ->
            val digit = romanDigits[tok]
            if (digit != null) digit
            else synonyms[tok] ?: tok
        }
        return tokens.joinToString(" ").trim()
    }

    /** Pull the first integer (digits or roman-words) out of a Hinglish phrase. */
    fun firstInt(input: String): Int? {
        val norm = normalize(input)
        Regex("\\d+").find(norm)?.let { return it.value.toIntOrNull() }
        return null
    }
}
