import pandas as pd
import feedparser
from collections import defaultdict

# atributy, co mě u feedu zajímají
# prvni uroven feedparser objectu, bozo je je kvalita formátování feedu
iafl = [ "version", "status", "bozo", "href"]
# entries, frequence nejak nadefinovat
iae = ["n_of_entries", "freq"]
# feed uroven
iaf = ["title", "subtitle", "info",
        "language", "link", "author",
        "published_parsed", "updated_parsed", "tags"]


def number_of_entries_per_day( entries, n_of_entries ):
    """Vrati kolik clanku dava feed za jeden den"""

    published_times = [pd.to_datetime( entry["published"] ) for entry in entries]
    pub_t = pd.TimeSeries( published_times )
    pub_freq = ( pub_t.max() - pub_t.min() ) / n_of_entries
    return( ( 24 * 3600 ) / pub_freq.total_seconds() )

def extract_feed_info( url ):

    import datetime

    d = feedparser.parse( url )

    ifs = {}

    # when we started parsing?
    ifs["feedparsingTime"] = tuple( datetime.datetime.now().timetuple() )

    for att in iaf:
        try:
            atrib = d.feed[att]
            if ( atrib != "" ):
                ifs[att] = atrib
            else:
                ifs[att] = None
        except KeyError:
            ifs[att] = None

    for att in iafl:
        try:
            atrib = d[att]
            if ( atrib != "" ):
                ifs[att] = atrib
            else:
                ifs[att] = None
        except:
            ifs[att] = None

    try:
        entries = d["entries"]
        n_of_entries = len( entries )
        ifs["n_of_entries"] = n_of_entries
    except:
        ifs["n_of_entries"] = None

    try:
        ifs["pub_freq"] = number_of_entries_per_day( entries, n_of_entries )
    except:
        ifs["pub_freq"] = None

    try:
        ifs["tags"] = [i["term"] for i in ifs["tags"]]
    except:
        ifs["tags"] = None

    # save whole feedparser object
    ifs["entries"] = d["entries"]


    return( pd.Series( ifs ) )



# Omezujeme se jen na prvni 25 clanku
def polish_entries_info( lc ):
    '''Vytahne info o clancich z dictu
    
    Note
    -----
    Pozor! Jen 25 clanku!
    '''
    if len( lc ) > 25:
        lc = lc[:25]
    d = defaultdict( list )
    chtene = {"authors" : "author",
              "links" : "link",
              "titles" : "title",
              "summaries" : "summary",
              "tagsOfEntries" : "tags",
              "publishedParsed" : "published_parsed",
              "updatedParsed" : "updated_parsed",
              "baseHtmls" : "base"
            }
    for clanek in lc:
        for key, val in chtene.items():
            try:
                d[key].append( clanek[val] )
            except:
                d[key] = []

    return( pd.Series( d ) )

def get_entries_info( entriesInfo ):
    ''' Zere to, co vyplyvne polish_entries_info()
    
    ziskat to info, co predtim delal goose
    '''

    import newspaper as nwsp
    from bs4 import BeautifulSoup
    from lxml.etree import tostring
    import requests

    links = entriesInfo.links

    dtb = defaultdict( list )
    for plink in links:
        # this is because requests follow redirects,
        # hence it ends up on true address
        artURL = requests.get( plink ).url
        dtb["finalUrl"].append( artURL )



        art = nwsp.Article( artURL )
        art.download()
        art.parse()
        art.nlp()

        dtb["sourceURL"].append( art.source_url )
        dtb["aerticleKeywords"].append( art.keywords )

        # get text of an article
        artText = art.text
        if artText == '':
            artText = None
        dtb["text"].append( artText )

        # counts number of specific tags in the article html code
        artHtm = tostring( art.top_node )
        dtb["htmlText"].append( artHtm )
        artSoup = BeautifulSoup( artHtm )
        chtene = ["img", "div", "p"]
        for tag in chtene:
            nm = "nTagCountsEntries_" + tag
            poc = len( artSoup.findAll( tag ) )
            dtb[nm].append( poc )

        # ratio length in characters of text vs. html code of the article
        rat = len ( artText ) / len ( artHtm )
        dtb["textHtmlArticleRatioChars"].append( rat )

        # ratio number of words vs number of tags in an article
        # this is IMHO better than characters, since tags can have long names
        # or css styling attributes
        ratW = len ( artText.split() ) / len ( artSoup.findAll() )
        dtb["textHtmlArticleRatioWords"].append( ratW )

        pageHtml = art.html
        pageSoup = BeautifulSoup( pageHtml )
        strSoup = str( pageSoup )
        strSoupSplit = strSoup.split()

        # length of code in chars normed to text
        dtb["htmlCodeLengthChars"].append( len( strSoup ) )
        # length of code splitted at whitespace
        dtb["htmlCodeLengthwhite"].append( len( strSoupSplit ) )

        # text words vs. number of tags
        ratWT = len ( artText.split() ) / len ( pageSoup.findAll() )
        dtb["textCodeHtmlRatioWT"].append( ratWT )

        # number of uppercase letters vs words ratio
        ratUT = sum( 1 for letter in artText if letter.isupper() ) / len( strSoupSplit )
        dtb["uppercaseTextRatio"].append( ratUT )

        # count all tags
        dtb["nOfAllTagsHtml"].append( len( pageSoup.findAll() ) )

        wanted_tags = ["meta", "script", "iframe", "div", "img", "p"]
        for tag in wanted_tags:
            nm = "nTagCountsWhole_" + tag
            poc = len( pageSoup.findAll( tag ) )
            dtb[nm].append( poc )

        dtb["rawHtmlOfPage"].append( str( pageSoup ) )

    return( pd.Series( dtb ) )

def get_url_info( entriesInfo, titles ):
    """Zjistuje, zda se url shoduje s title clanku
    je tam primitivni ucelova funkce (delsi slova prispeji vice)
    jeste navic zjisti, zda url adresa obsahuje specialni znaky
    
    Parameters
    -----------
    ASI NE! - Zere Panda serii, kterou vyhazuje funkce polish_entries_info()

    Note
    -----
    
    Pozor! Linky uz musi byt skutecne.
    """

    import re
#    import numpy as np
    from difflib import SequenceMatcher

    check_let = lambda x: True if x.isalpha() == True else False

    corespTitles = titles
    links = entriesInfo.finalUrl
    storeD = defaultdict( list )

    for title, link in zip( corespTitles, links ):
        lsp = " ".join( link.split( "/" )[3:] )
        title = title.lower()
        hled = re.split( '_|/|-|\+', lsp.lower() )
        hled = list( filter( check_let, hled ) )
        # print(title, lsp, hled)
        # zjistim, zda je nebo neni obsazeno kazde slovo

        rat = SequenceMatcher( None, title, " ".join( hled ) ).ratio()

        # print("Hledam: ", " ".join(hled), "\t", title, "\t", rat)
        storeD["matchUrlTitle"].append( rat )


        # weird occurences vs textual
        numbAndWeird = re.findall( "[\W|\d]+", lsp )
        countDash = len( list( filter( lambda x: True if x == "-"else False, numbAndWeird ) ) )
        try:
            normCountDash = countDash / len( hled )
        except ZeroDivisionError:
            normCountDash = 0

        countHash = len( list( filter( lambda x: True if "#" in x else False, numbAndWeird ) ) )
        try:
            normCountHash = countHash / len( hled )
        except ZeroDivisionError:
            normCountHash = 0

        allWe = list( filter( lambda x: True if ( ( "-" != x ) or ( "/" != x ) ) else False, numbAndWeird ) )
        countAllWeirds = len( allWe )
        try:
            normAllWeirds = countAllWeirds / len( hled )
        except ZeroDivisionError:
            normAllWeirds = 0

        for dk, dv in zip( ["urlCountDash", "urlCountHash", "urlAllWeirds"], [normCountDash, normCountHash, normAllWeirds] ):
            storeD[dk].append( dv )

#     mns, std = np.mean( artMath ), np.std( artMath )
#
#
#     cd_m, cd_s = np.mean( storeD["urlCountDash"] ), np.std( storeD["urlCountDash"] )
#     ch_m, ch_s = np.mean( storeD["urlCountHash"] ), np.std( storeD["urlCountHash"] )
#     aw_m, aw_s = np.mean( storeD["urlAllWeirds"] ), np.std( storeD["urlAllWeirds"] )
#
#     cols = ["matchUrlTitle_Mean", "matchUrlTitle_Std",
#              "urlCountDash_mean", "urlCountDash_std",
#              "urlCountHash_mean", "urlCountHash_std",
#              "urlAllWeirds_mean", "urlAllWeirds_std"]
#     vals = [mns, std, cd_m, cd_s, ch_m, ch_s, aw_m, aw_s]


    return( pd.Series( storeD ) )

def feed_that_all( url ):
    '''This collect everything from above
    '''

    defaultInfo = extract_feed_info( url )

    entriesPolished = polish_entries_info( defaultInfo.entries )
    entrieInfo = get_entries_info( entriesPolished )
    entriesSim = get_url_info( entrieInfo, entriesPolished.titles )

    # feedparser object of entries is no longer needed
    defaultInfo.drop( "entries", inplace = True )

    entriesTotal = pd.concat( [entriesPolished, entrieInfo, entriesSim] )

    # thanks to mongo we do not feer structured data
    total = defaultInfo.append( pd.Series ( {"entries" : entriesTotal.to_dict() } ) )

    return( total )
