import re
C={'ক':'k','খ':'kh','গ':'g','ঘ':'gh','ঙ':'ng','চ':'ch','ছ':'chh','জ':'j','ঝ':'jh','ঞ':'n','ট':'t','ঠ':'th','ড':'d','ঢ':'dh','ণ':'n','ত':'t','থ':'th','দ':'d','ধ':'dh','ন':'n','প':'p','ফ':'ph','ব':'b','ভ':'bh','ম':'m','য':'j','র':'r','ল':'l','শ':'sh','ষ':'sh','স':'s','হ':'h','ৎ':'t','\u09dc':'r','\u09dd':'rh','\u09df':'y'}
IV={'অ':'o','আ':'a','ই':'i','ঈ':'i','উ':'u','ঊ':'u','ঋ':'ri','এ':'e','ঐ':'oi','ও':'o','ঔ':'ou'}
VS={'া':'a','ি':'i','ী':'i','ু':'u','ূ':'u','ৃ':'ri','ে':'e','ৈ':'oi','ো':'o','ৌ':'ou'}
DIG=dict(zip('০১২৩৪৫৬৭৮৯','0123456789'))
HAS='্'
def is_cons(ch): return ch in C
def norm(w):
    w=w.replace('\u200c','').replace('\u200d','')
    w=w.replace('\u09a1\u09bc','\u09dc').replace('\u09a2\u09bc','\u09dd').replace('\u09af\u09bc','\u09df')
    return w
def word(w):
    w=norm(w)
    units=[]  # each: [roman_consonants, vowel, is_cluster]
    out=[]  # sequence of tokens: ('U',cons,vowel,cluster) or ('X',str)
    i=0;n=len(w)
    while i<n:
        ch=w[i]
        if ch in C:
            cons=C[ch]; cluster=False; first=True
            j=i+1
            while True:
                # consume hasanta + consonant chain
                if j+1<n and w[j]==HAS and w[j+1] in C:
                    nxt=w[j+1]
                    if nxt=='য' : cons+= 'y'  # ya-phala
                    elif nxt=='র': cons+='r'
                    elif nxt=='ব': cons+='b'
                    else: cons+=C[nxt]
                    cluster=True; j+=2; first=False
                else: break
            # vowel sign
            if j<n and w[j] in VS:
                out.append(('U',cons,VS[w[j]],cluster)); j+=1
            else:
                out.append(('U',cons,None,cluster))
            # trailing candrabindu/anusvara/visarga
            while j<n and w[j] in 'ংঃঁ':
                if w[j]=='ং': out.append(('X','ng'))
                j+=1
            i=j
        elif ch in IV:
            out.append(('V',IV[ch])); i+=1
            while i<n and w[i] in 'ংঃঁ':
                if w[i]=='ং': out.append(('X','ng'))
                i+=1
        elif ch in DIG: out.append(('X',DIG[ch])); i+=1
        elif ch in 'ঁঃ': i+=1
        elif ch=='ং': out.append(('X','ng')); i+=1
        else: out.append(('X',ch)); i+=1
    # find unit indices for schwa deletion
    idx=[k for k,t in enumerate(out) if t[0]=='U']
    res=[]
    nU=len(idx)
    # only apply to Bangla-letter words
    for k,t in enumerate(out):
        if t[0]=='U':
            pos=idx.index(k)
            cons,v,cl=t[1],t[2],t[3]
            if v is not None: res.append(cons+v); continue
            # inherent vowel
            last_unit = pos==nU-1 and all(tt[0]!='V' for tt in out[k+1:])
            # anusvara after: ng closes syllable -> no vowel needed
            nxt_x = k+1<len(out) and out[k+1]==('X','ng')
            if nxt_x: res.append(cons); continue
            if last_unit:
                if cl: res.append(cons+'o')
                elif cons=='y' and pos>0 and out[idx[pos-1]][2]=='i': res.append(cons+'o')
                else: res.append(cons)
                continue
            if k==0: res.append(cons+'o'); continue
            # medial
            nxt_unit_last = pos+1==nU-1
            nxt_unit=out[idx[pos+1]] if pos+1<nU else None
            # delete schwa if next unit isn't the (vowel-less) last unit
            if nxt_unit_last and nxt_unit[2] is None and not nxt_unit[3]:
                res.append(cons+'o')
            elif cl: res.append(cons+'o')
            else:
                res.append(cons)
        elif t[0]=='V': res.append(t[1])
        else: res.append(t[1])
    return ''.join(res)
def sentence(s):
    s=s.replace('\xa0',' ')
    parts=re.split(r'(\s+)',s)
    r=''.join(word(p) if not p.isspace() else p for p in parts)
    r=r.replace('।','.').replace('ksh','kkh').replace('jny','gg')
    r=r.strip()
    return r[:1].upper()+r[1:] if r else r
if __name__=='__main__':
    for t in ['তুমি খুব সুন্দর','তোমার নাম কি?','তুমি কেমন আছো?','আমি ভাত খাই।','আমার মামার বাড়ি যাচ্ছি।','তুমি কখন বাড়ি ফিরবে','কমলা করলাম পারবে','বাংলাদেশের রাজধানী কী?','আমি ক্ষুধার্ত','সত্য প্রিয় ধন্যবাদ','আপনি দয়া করে আমাকে সাহায্য করতে পারেন','আমার ভুল মাফ করবেন।','আমি সাঁতার কাটতে পারি','তোমার সাথে দেখা হয়ে ভালো লাগলো।','শীঘ্রই সুস্থ হয়ে উঠুন','বিশ্ববিদ্যালয়','ঢাকা','আজ কি তারিখ?','আমার ৩টায় একটি মিটিং আছে।','পড়াশোনা করতে যাচ্ছি']:
        print(t,'->',sentence(t))
