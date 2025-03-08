import asyncio
import traceback

import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
from web3 import Web3

address_borrowed = {'0x474EEEE2D36d376cDa238fF5ffc7c97A393ebC5c', '0xbF3e9A466037afB7E1937322E0e2807a89218475',
                    '0xE6D8267cFaa4e2B39B45Eb98e2A533eAb0821959', '0x63eBA96D9A9ead17Ec564136797e824903aDa73A',
                    '0x161B401D57c1CF0a77d831639f2Aa954e113Ea97', '0x516E5B72C3fD2D2E59835C82005ba6A2BC5788A4',
                    '0xe74226593535290Ea148dE0D4a5Aa549EC24CC05', '0xFbd9275BF42f21B7CB857E6C00FFCB99443718B5',
                    '0x64B942220E4C1906bfeD25827FAc9d80B394b0Da', '0x6f5a8A35fb10EEcEF9128f407a0fe67B898556CF',
                    '0x4aD21BB13288ADB4e79268dFb894c4f0219F00D1', '0xF630f7C0b03884878C3eBd5Be0f7E439e39A0044',
                    '0x4a4E5DF4874e405912b3cAb2cD18B889ad4bE220', '0xF07B0dd17a9cF8eE8613b548210aF9Bb26Cb5Dae',
                    '0xC44fD102415FF62769A4e37C70deA27033a5291F', '0xff0C6444cb0fA6121A85e838219354bfe2e1556B',
                    '0x1006faB5823537d8fcC1C8a19C10632e87C758Df', '0xb53Fd34336F2e388C55920F1264b143A11D47432',
                    '0x6FbE6EaB3053fEF0DA871807346B0B40E989840f', '0x819aff480ADF0bb132E3127692e1CF6D0004e451',
                    '0x9d862DADC038E52252faA3897aA884e494A40468', '0xcD48996795E10903787a2F6bf8730f6368A8fd0a',
                    '0x0dd222BCCcb09f1d013C6086E7b8174dA4bEB4aB', '0xb953FF993BC93E30022CaD135D1eB987553b9d6a',
                    '0xe2680C6C726D2fBD9f8766e6c6d0bfd289414122', '0xFe51263Bd0d075Dc5441e89Ecd1F6D63fF41E02E',
                    '0xE7EB077D77f09b469B2ea8548AA860b137039977', '0xc60749f1941A6cA01aBBF7c99597f14AaD47FD21',
                    '0xC48B0a61326CCe04d654c5774c355849B873730B', '0x1309c007567a71b393094c21E70bd2647356A352',
                    '0xc98F060eE63e0278b46EaF0A2a201c18d7EceceE', '0x4dCbB1fE5983ad5b44DC661273a4f11CA812f8B8',
                    '0x3e5e6a6c9c8654A5643438eE4858A8BD1118d01c', '0x009C61150F8AC88c5eD9Ab763d0E86AAA5f3aAEb',
                    '0xd3ef6170811406Ff050111aaE4C648224F0af233', '0xfe41af0405B74571B3234d6D34AC0f83676072D8',
                    '0xdB5f00B55723eF190A041F9f3f7DbD20086Bd79c', '0x2Ea0963fF33E420AD67cd736d1f44CAC2fd4adEE',
                    '0xe14A0c94758b2d7E9A22Ce4E046c5f8762A672ff', '0x8A2777C328d845DA5F2c3a3007CF4f9c97C66262',
                    '0x19BA1abE64245f0a9eB12B9efCC94167f9a05064', '0x99264C01ACffd3126ac37fB895940c0b5bb8fb7b',
                    '0x192b2aD472D0DBa9464dce7E479ceaD57175F466', '0x0c9253c89F4818f0072691872739018436c3aF6b',
                    '0xCb15941180ED7CfF8B3547117eCA6b78cbdEaF9C', '0x05272a105C6B9E8D8b991Efc5708d9Ae4F2a6e86',
                    '0x7E6601A0Cb2B5aE129c09661846a053ea07223Fb', '0x3D7209732AEa29cF3cBFb468acCF627C5B09047a',
                    '0x3e23FB0715E9be36Eb8D02cE7E50dDE80494a90B', '0x90fBdeA901328509EfcbF80560e5dA60ae15E17A',
                    '0xbeEBc0c769a24f94681d05751fCDa51Fb780931f', '0xe7991622DeF299B2ff9d227E76F9BaAe5D9D1C26',
                    '0xDB611d682cb1ad72fcBACd944a8a6e2606a6d158', '0x3f37bC2DBb082128273E6bb533F80Cd63e7A4200',
                    '0x908fac3A4A7853F6dB588BC17BDE05adc221a1db', '0x2A695fcb803f336B869bEBafdbEECB6448f096B7',
                    '0x88b7a44CECD526cd2D424B0A4Cc2bbB26341Dd8f', '0x292646D33917450e9B5f6e59e408F4537703cac9',
                    '0x93e5204E7033483985Bcc94E48283f3359b2be69', '0xcF824E5babADf846FB2b242bE274C8FDc0f113a9',
                    '0x32706B2872Fa3ad592Ad4A7317C4DB1cDFc34787', '0x12e1b13555D430f0be94E2F5D785DC320e886B46',
                    '0x941f35E1b65b02309dcDcAf00eB8c8E3fc6E175d', '0xFAfeb09ef6282DDeB8748Dd19FE5B16dD9F38e0b',
                    '0x5892Fe47a8ddE5a51bA2c75c3760689C393323D9', '0x61F0472cdCbA25788a54D200331b6937112dBB75',
                    '0x2cFFaD5c50aD5F0c6b2A1348648B64387C000aD8', '0x370a5275F69CB3C2E76CFe575cF7f846f906b34D',
                    '0x48F544a44E2Ed51907363Ae65fd693cCF5F0a38d', '0x42490E7C2d1403e2C2683cc61339C69c500C98CB',
                    '0x54494827316C7C6627908A9261AB13Ac0A5222E3', '0x759253A07Fb2b4482EE3Bf69cb527d2Ea1d7608b',
                    '0x99F6D2bbd6a2dA57830248B73ea558f62Ebf9870', '0xdaC51643888be5414f0272b9fEEF97EDf723203A',
                    '0x0D7D9AcF85FA0Bb5eE25bd8016B7c0f5A711c893', '0xDF7061AC5F1282f78eF8b70CB1913CDF466956AC',
                    '0xF2f17254d94769f38f92aa3dAE5b6e0077d618dB', '0xde35Fc05290030d2057E303d6965c485F9eaFa71',
                    '0xf2F3e73be57031114dd1f4E75c1DD87658be7F0E', '0xe6Fc4FB33B6D3e7d3B7574dAA1B8E671A6079900',
                    '0x151b1bCe597a8Fa247636442E1110F6d883C5ff6', '0x1311e163B5A723C8baa067C2585324A235Cf1F6c',
                    '0x146c92481E95C838868aca795D353e202C12872F', '0xbF87006AeFe8a450224B9dD139583321664E354F',
                    '0x48553662B61D9B246206fdC5Ee06C643ED85cb00', '0xD941c574bfC0C8e3DeFA9F572291895Af3a03458',
                    '0x2aC69800Dc45b1a484225E1a5F6eF7D1C6d10d7e', '0x59511e5B333D7ca552BB32384424b34A45b972B8',
                    '0x18b520d4716acbD70F182C09e8927126F05a0743', '0x1AE974AeDF00b84577Af4919570Be14DC60e3e40',
                    '0x3bdF5966ef2a98D3621C7C3b9978A1D2965596b9', '0xe55C83a72ed2f9DeBBc3eDC8037f5AA82086E9e8',
                    '0x4761495Ff0A34555287D21AB8a32431eA0CBe207', '0x79D1a51fbc328ec9741Bf5026d2DdaD9f99f99CA',
                    '0x2326D4fb2737666DDA96bd6314e3D4418246cFE8', '0x2B2e8f249d40852f4b9b4D76519e41128D330a80',
                    '0x2E76Ad51473F2e7E8B51DBA43e0D27608D3e20A9', '0x31FDCD0cb5d698A6571432fCF32Ca6b287Ab3D30',
                    '0x4bD4e5818d30B47bc771E5fD271Bd9c15570Be30', '0xaebb8FDBD5E52F99630cEBB80D0a1c19892EB4C2',
                    '0xfE4d9D4F102b40193EeD8aA6C52BD87a328177fc', '0x45cEf894B1A1bDE4c6677A20F8254E5048923C1c',
                    '0x117885dCECD5929dE68dee13E62AF72D0170602F', '0x7776DF3141eEB57bC414720CD1E37eBBa506d3F6',
                    '0x41687b1349A6dE0Cc947c9E154D5D221e99aEbff', '0x2E142d386019361f645F948797Ed6924fF7A294d',
                    '0x2a47A9Ad17bD1BBC31a4Ee8a44d0A183a3e46693', '0x4eb8F786162e206FCBFB7BaEcE4D47FcB6b068e2',
                    '0x3Bec5a2012AD1A6E7a6868B023944e49087E9356', '0x615BFb6ddDb6928a8588E386287Cc132ECF18ead',
                    '0x111069efB5241D44F527F2F28eba5d26D7A2f8f0', '0xb5C4402fF7cBE97785DdDC768c4E3a4f033474fB',
                    '0x56c915758Ad3f76Fd287FFF7563ee313142Fb663', '0x54079F704D7123b8377236808E5A16841c2B0300',
                    '0x59C3b35Cea05214C350f017B59c11bAC8be3A7d7', '0x93d730ff5a6e11D0b7F57F053F15d8B85A582341',
                    '0x16FA6B8FCC2D5F459600713cF961E349067a278c', '0xe064fd9Cd72Ae05044eA5414d1653a5867feA112',
                    '0x2e85ea08ADEd3EE0D9074779A17456d8377445A3', '0x8A9087bc1A48cA3b2A25499b37eB70ac13E3F360',
                    '0xA8e09D93ca028D43BD8241882886e5Ac7AD5112f', '0x7677d22ECFEE855E7162557b3c58ef9b892d4A9a',
                    '0x8304F0ca0ecA7390aEA0660bCEC8C14b0080D272', '0xe550Dc4ae6B6C4D693c6eBA53B58dA162ac53e58',
                    '0x5A477CF891d4603cD40679155d09B5D37C48CF2c', '0x8708d4E0D37402A89f8c5836878c86ae33543ba0',
                    '0x05Bd092E09aba556CE23A0F9D8034D00C3ECB8Cd', '0x1Cb7F3EaB52BbE5F6635378b09d4856FB43FF7bE',
                    '0x290684C9F3b308BfFbBC09566d8418A639Ef7e1C', '0xc00d8dAC46b1F8bcEae2477591822B4E5B0a7C6b',
                    '0x14975679e5f87c25fa2c54958e735a79B5B93043', '0x7E7c633a0765694ab8BB1271e1445642aE093d53',
                    '0xC83645968AafCadcD1b6b399124EF4D18CB43f3A', '0x73B13209C764358E132d0E9DCf30642BdE0b5614',
                    '0xeD7f2016130CA5083261079C7B869cc3ab82181a', '0xBD310De6bd2983c4ee5aD3ad7Ed90f923CD59039',
                    '0x1109297e392d92c1613fdbdF30579a0215c20Da9', '0xD7b2879C8922cd704E41E8CC1f18f6994D6B7C36',
                    '0x66E0a0cd41a6B9971e22f3d7b3bB042A038F306B', '0x169DD65B89e365ABA3E826efbD3688F429820E97',
                    '0xa6E72cCAc7dCd1ED713ED49f7b3896cf1958A558', '0xaBA7aDCadE9754304E558970089Af59824135bDc',
                    '0x8dB0FF0e6F52A9fF8a324957D5338647D651dFc2', '0xad63412d71457772375E627c895bF486CB2BD938',
                    '0xA32C1937f5B05B26bB2923848438Fe95e5a868eC', '0x29E55Ce2e13dfA4E1982Ce43e8f4991F5b450c80',
                    '0xD51Ab3249CB64Daa72EfA15Aeb0248bD3a823368', '0xe75A4D6469C4629b86202487aa50D213d6436DeF',
                    '0x2Ec8650319476C666CaB5a603b1C61150Ae9C6c3', '0xa4d805413010Ece2Ee1d59C4826cA66292Faa8FD',
                    '0x8392C202D0fccd7f149748C59dA28d2d1484daBd', '0xEc8E259978e19368A74715C6EA11cFE934b07333',
                    '0x4bB24C2Ec5db591E5aC9Dc29B5D500E399a40d86', '0x1B8021FA7154724a3e823D087094Fe637Da3bDf2',
                    '0x948e8Fb09Eb34CC899e0301c1C999Dee2bA14F49', '0x9f87cAd4feb77F82b015B97a4C37c336652Ac2C9',
                    '0x192820CE84FA9eb457Fb228c386fE0ed22F7E33C', '0x6A873E22e11c8D77731E213D70B9083a46ec2c1f',
                    '0x1624d2A82a15A3691D86Fe1E62a871cA6779A0ED', '0x3E61DFfa0bC323Eaa16F4C982F96FEB89ab89E8a',
                    '0xd027b4D10ba1e45E97854B190d14A5d892a6C787', '0x8aD09925806C9ddA4B1aE98fE35b2761FE0Df117',
                    '0x87e1523E9866e0F2fb925D46F2F253641D3437b5', '0xB2043c543bb60Fb7AA7265CdcA359A35C4Bc09fa',
                    '0xB755885151DF63f2d7d3431C66f48c69B83850cB', '0x2AD36D1DcF07521eC179F690152f34Af405E6Da0',
                    '0xA7A8a51DA52A1e7AB1706fc5C9d99F0CbB357A36', '0xB29d600b7B18459d1eD6ea180801eA7539C36ffc',
                    '0xC89AdB478E8B67bc2C25D1b315802bfCe9B3a549', '0xbBC372411dECB67D6A169ecb5b8Fbed378ffDC2F',
                    '0x2bb8Ab3C2A9837de97A83c228A07E16928B4f07f', '0x22146a562150778032E982f1fCbA901F480dee0D',
                    '0x6763DF505F7F343FbF69f8D5d87433dCdAE2195A', '0x887b4B08BA619D629FFf17DC74380640BF55702F',
                    '0xaC83189208b4f88233ed4d4e5ebA7600276Ab4bE', '0xE7cbF5f2922D1f69353Efc144c916A79C29A3e2b',
                    '0xCD7655832ce7012AE3320851b2e45b1050AA9c2F', '0x3159BFBB1f89b363C24Ead3AA5AAAfe400269E69',
                    '0x474F18a13762dE5F18E5400A026a19B68c35BcaD', '0x3A13186E9644E8862E24F952002dC6e3Ddc83ebe',
                    '0xDF103F15318B9671d100208Ed9056cb18662eEa8', '0x5573773B310fF0C0ff0410Fd48Deb12b8a315230',
                    '0x80485C1015d21764Ed8f204cc4D124Cb7fD1940e', '0x0574215B0a39119c84Ca17F1EC83418EeB5aDa8e',
                    '0xE9859486E8C8f1493C3056fD1D0C442A3375f074', '0x6d39d82a7e43DD567Efc03ef28EE73663f2AA515',
                    '0xA10d11eB58c417b639fa977c297275e6db6acFCf', '0x344d9C4f488bb5519D390304457D64034618145C',
                    '0x78e34FeaE8fFBBD51d6ef4949E99aebfC5ef5044', '0x8a72539c47Dfc0a01Bf8FE8f741156F169301384',
                    '0xA79aa24198217283C017Fc8ad92C307F564a95A7', '0x7c40D0D34CaB1DDccE1C63a93c8BaD1857661067',
                    '0x1Ce4C7977bf92cCf62B1DF6E97A55BC33E5E6B2F', '0xd5bE59dbe8548503C82E60e18297EcaFA6e6cF29',
                    '0xe989Ae62c6D39BFBC919253EFa4194454b575b9A', '0xD567F687B21127016C9F6DdAc5674D9d045BF1bA',
                    '0xc38AaA50Db98e0C5d60e5873FeA18572e6E2Af94', '0x591584f3BfcF142a346ea6324772411a0b40fF3c',
                    '0xe890BBb728dF9C5C92818D3F0787704ba7710a87', '0xEA19b97a1523ba7796c3c9075B243E14D3995474',
                    '0x35DC3AE8ab20501a720c6b8e247d7EF86F111872', '0xdFE201CeDC41f970D43f95674d6b4bE02dE784dD',
                    '0x205A0551A7244d78E504CcFBFbB6d2b91d8f3D54', '0x729bD77a297fD16fAf702F72B0FE4c3Ee99840B3',
                    '0x61d345369925129c5C97374051C410A62a19B3c8', '0x3f39E425dF7e59d64339130b3Cd3d34cAf1e6963',
                    '0x8464A7815002e3991909212F465Df09789601093', '0xcc900e6eBA152c917CA34856bCBcc60152e1EE76',
                    '0x98d67e19fd06371149761cB4776dDCc59dECE83D', '0xD1247687708d1fF50b024Ff2BD27d0F07eD19fD1',
                    '0x0bBB4d30EF79a295cDC9FCfb263327b2f5B3848C', '0xf039C7aa9CC9aAe826938Ff8c23fB7EEbA084087',
                    '0x69A67B6cEd7DfAB150458cB3c2778a2fC2b91694', '0xddF279149Fb83ffEE7D54A36f8a04D363081faf5',
                    '0xa3577f7828A8AA42d3F31CfEb1E48aC8Cc698feA', '0x9cAB108E2740798BBA37f9A24F0805b3E00B9ef9',
                    '0xD985591993FA6e42F4355cef80CCBaff6a5EBA60', '0xd3fC2D1f183f509AAAa814541055A11a0358d8E9',
                    '0x940cee863dDA2E02747c00908D3CBAa1C0F3dE99', '0xd544BeC5b01260ED206F966ad982513138939d2c',
                    '0x00170cEe97849d049Aed3DC5237280bAD4230E44', '0x2Ea7CcE60d849870aa21659190CC747edE2BEbA1',
                    '0x58AeEBfb3646902DB19580c1E45eD10F40272dB6', '0x7C39d57B97c7e3ED305484f5513cCfC2089cDe90',
                    '0xdFE796344d42a7E8AE8c0E2b93d76A26f6F3c457', '0x2FcEE421E8Fe1cAfCB1f745d2088d0efE832D779',
                    '0x5Bbc9C65a82B12a61c732ea449c6eFe47fd40542', '0x60c4BeFaa67C2A8de062dD43b3067DFBC97D8577',
                    '0xa58627a29bb59743cE1D781B1072c59bb1dda86d', '0x2F03CE8B4e68b860Ea89a59010F964E377fc058C',
                    '0xdD9BD62D1c08210fDDa6f841eD5196B45A939625', '0xd9ecd2cf6e19F10463D81599Cf58CFB54a80CBf1',
                    '0xfb7945E6494c96c8EE7A45cC6e20A912A3f1BD5b', '0x1e121993b4A8bC79D18A4C409dB84c100FFf25F5',
                    '0xfCD218cc65bCa1dfe5fee91e8a2182d5643B094c', '0xbc8c35948150fF1Ed2d3374be687a5Ae4A9e00Bb',
                    '0x2fB9710D36577a9154de8Fe8DAA7b35620C9e612', '0xD4371C3843D14753a1F52302b24d1719e7F57d3B',
                    '0xaf0FDd39e5D92499B0eD9F68693DA99C0ec1e92e', '0x3413d6DB7A4718Ed023f804CE5c1171EB84EEdEe',
                    '0x0645736eeCfE8B572cbabb885eAaDe641B659846', '0x4a1D41E1aa65384AC3021D144aF5056a086b165b',
                    '0x97A4f0fc71074E0689A5D0aFa17aEE07882B2689', '0xf5A3bf3064083239B79A46EaeCC9F90c790D1cf1',
                    '0x9D894293a144f3eF7E89df17Dc7C98d1e0fA3850', '0xc8c7b9d46fDa59Ea210318508c16ECB8F8C10f8a',
                    '0x5C44368C0Ad4C446842738BDbf8f2Bbf9876546e', '0xc42Aa71ad8F3f30aFc8915CB80689bC69CA1B987',
                    '0x9Bd69Bae91efEce48fc2c704bb8430d903ba7f5F', '0xF2f1C957109122732033cC0e2B1A53D3CFbCcf9E',
                    '0x5FE08FFF7af925e92B68B6B17c0f8457B90d1697', '0x7580E305f5a8A46a36c43A8cfb6ce1bA2c3e7fAF',
                    '0x73831e7c600F48cebBbfF957b466be8e5c087F34', '0xD97CCF2EeCa2EE80f2D0b2ef0A33cDde9aAc1a74',
                    '0xf32FC1113f4769f59984d615e91A8e94548F2790', '0x68258012DA3B933a81617FD08c9382a60B87cA98',
                    '0xADa865E174e7b85535b458B1B5712023969739cf', '0x276B9DaE2b199C437b2Abd43746bea503B55234F',
                    '0xecC25630B09f65E095e56cbb1e957CC631FECCd5', '0x0Ca822FE0A177479B93e461b52AEFacd5ed81c43',
                    '0x7e9139b30974660AffA1DF7CB9D1207aFcD98b01', '0x319a6fC1Bd3086E7cbceB3cd4057a4521363ADb8',
                    '0x62Fe21195eD84D2d9299B5d66C99cE49b52D89BE', '0xd302DfF76D5fDaDdA32cFd667753e54045eC7cEd',
                    '0x01105f5822fb45D42d35Db379E62a1D60eD7086b', '0x44a19463C22337Cf80CD4Edf4B2EeBa94d900450',
                    '0x61A3e252fD3E403e84F3e5A71073B540983b9936', '0x9b50682Ee30CF0A6267e78A2Cc2c796B7eCeF062',
                    '0x17ad4E76e67E9937A2B2EF882e4042Dd00Cc60F7', '0x6a4bD8e68D568DbdF883A8f1a48863108A3e4964',
                    '0x3Dd7D7db118028783F7018A25bB90f6a6449df13', '0xCFFbf2640d2bf8E9A03e9E14FdE31D71C1971139',
                    '0x68fdAe7631C469659A338Cd84eDCD5B11F800Dee', '0xE3fb06338b886809b94B4208b9217F5DD85A406D',
                    '0xD3aD98CcA3ab052d58d6dDD1D14703801fD93435', '0x0F3b97804161921EBd8D453966C53995af3Fcdd0',
                    '0x075764e96cD7e3426Fe0f99894F40Fada3686aF9', '0xB1dB096De2A713DBb6950Dff2EaFB76521881863',
                    '0x686e3520E5A28e8fF9693ECed99dAA3efaB4b50c', '0x869C98f94C1A15118Ca10cd86F74B1A3550Cdd29',
                    '0xA077b54582e5d05DE3873b080ca9Ed4b59acF015', '0x0487fA0bC54d3CA4E0977583dD15a7E1d26ad82A',
                    '0xf9a6eAB21B54196dDF7E9BAf79Be2188f32681db', '0x561e82F825Cc487F2d07310839F3cc68eC877e10',
                    '0x6780ac060FdcBA20AE02A6197c84Bdc70CF8716B', '0x999910348d1ac3010c03E4D899Ad4CAA8cE99999',
                    '0x29F88907c607c3D2036F3091F131783C13551e1a', '0x0fD6f65D35cf13Ae51795036d0aE9AF42f3cBCB4',
                    '0x8A4122df116Dbad7Add01cC26AC66B8D418bF2d8', '0x0911C522532020845A7EB5426D44D3D9B9521FD9',
                    '0x5B0aaCAD28E8BD29778e27BA8C0a05C0161Ef1A5', '0xd1b7Be1B0A9b157389fb713F1fA18AADbf1a735b',
                    '0xA20f9874dD1EdcCBEC1BEDA894f98F45069E4205', '0xa2C77Af219A0e7A41f7b7a5F6981c5e85a9D883c',
                    '0x80DC1C9f26fb9f979189E7806f167901940bDe64', '0x95E5816F061D643FC48b8F89C12D0e34949feA77',
                    '0x53DCB1143F7F2Da6C9E182d4d42eC45b0Ffa5726', '0xFD26f25d6588b752a90e600AFF038A654D64a42C',
                    '0x0b0a1BdbDFE319F03661f210F12Aa25Cb3FcfDf1', '0x47804066a74911C1C091bc93829aA818D81d9239',
                    '0x6b5fa3E2C7176b0bFB28C7b47269469fE2D2eBe9', '0xd446089cf19C3D3Eb1743BeF3A852293Fd2C7775',
                    '0xcc7a9f564Ae405EdBa33ffC0332bAD8451c63E41', '0x70Dd7301EdB89Dcb0FdBF26e899589792BaCB5Fa',
                    '0x4e516Eed9931F0Ec00bbD92a2441ca75e23d567b', '0xE87BA48E758a4e8EB070C73A494019Ba9A823Eba',
                    '0x6E80Ff8d90327777477A301335A03851Ce44a19C', '0xFC88e456b3a5620E63A449cE429dCcF2687cac26',
                    '0x7e2a3694256E13705eb7924649e5E267F5BC5398', '0x0A13c3d5ACE452f86CBBaC4247Df16EBaf7cC5ad',
                    '0xc69579EDAFAbCDA360936acb11043A555eb86b34', '0x8DE357C6cD4F5d49B0BA18e2CEf83f0E25693445',
                    '0x4Cf58B6FB1c4016A0C2EB4A35DF136Ce9561D52E', '0x7A70EcA937f10234c42b4dAED0970FAe6f88DF15',
                    '0x4545E97854655807732b30057A4D4181e08BC2E2', '0x40EdDEe537AEaD16c2c7E3DacfDCC8e7DB49C596',
                    '0xcDc8BBC2C740E44e9231dc3a8842800aa2433d18', '0xf42685e0278852607A62cBa626f44e1Fe430E3F7',
                    '0x1171BAC7e25C2973468652F17B2b066E3E0dA3d5', '0xAb856273e4F9fB385744Ef971998eB1d2De62e59',
                    '0x0f3563D5A39f6Add7E60630BD14f9D8dED0CDC5e', '0x4E36C2783f689B81dF6688CEb1B9aCeD2B23951B',
                    '0x6BFdc44450E5c5E535b114b147f10710800Bf0Cb', '0x617eb09D7869de4Ea8a9768C5c657ff7C2D80F97',
                    '0x0A66A105EA8a4FC5A0475B37Cd4be050621b95D4', '0x9bf672D537416927b5d82148566934a39b92557b',
                    '0x26Ba536578ceC9F73b594DE9542C5A36E07b47E8', '0x1601e714a16d4b5F04911a42726a637e28DF27fD',
                    '0xdB5d05176f11d71eA050da9bE1D51C6C54BAEC26', '0x54bB766E58B8D541c15B271E0D97783f39a52b3D',
                    '0xc66463Cf95c3a3210DefC8BC40546dc687B86796', '0x9bAf8e56dfA875e7Cd4378B8838425913d367BEF',
                    '0xc92447312820f846864804c89Df633d128C339DC', '0x0c209Cc80faA42031484621788Ef97CB1A9C917e',
                    '0xa7b5400973EE73d360F4aDC88a011D7Be388FD64', '0xf4aEC9871916762Fd2F541fb2f193351C0Db329A',
                    '0xaE3C1FEe591Ff0Dd95D41Cb48C37922Bb64E3c81', '0x6ffAE491AAf5F370B30f0B53641DD4F39BF31167',
                    '0xbDfA4f4492dD7b7Cf211209C4791AF8d52BF5c50', '0x56DeF29beA7bbDe9FcC58057f78C6100d7Eeabc4',
                    '0xB1946a10b9189206340BF3C1cEc266eC80fBacDb', '0x8d945AcA57CBe793507bcCaba8cd77bFe117f255',
                    '0x9854A00286Df9F9F79A4953934e9f6D522A91D52', '0x1fb24FC41ae7347886E1dbb74F3F2716d20d44Ce',
                    '0x93a0Fd1953Ab7aF256fC6e292472Aef8c4cA3f6c', '0x2284a9b9bD207039Ef835202D16B37B6C98F376a',
                    '0xa6Fa61935B0442fE390c54285B45Bde93b0D4c01', '0xDA35fb31B343e790C1f6639cA5634e0d91fF8B7A',
                    '0x9E0bf7fd04960e337298175B0Ab1b1d5efc69B78', '0x8b34b1270F0E3c9afC9e37A048f042a69fFE9AAE',
                    '0xC499Ed2CDfA468122e0ecf454523547cD29c8951', '0x82C63De74A0A2Fe875ed643011562f07c7Ef65fa',
                    '0xA3cD31949438e49Ff7411A23AA844a9Ffe8D02CD', '0xF6803BCCc299a7cf614E2baF4A48EFdCd38dCB29',
                    '0x344d092b718D3C1e95d1A0740a5A70d31CE816E2', '0x94F9FDb43A2b98B2920BcD37848D2165F2007511',
                    '0xd017cb892a05929217151a16ae801bcA5325f0AA', '0x308048bed0306d3F1471863ee08464184A2E63DE',
                    '0x4371eBAAefEb8e56ea8448787508EfeFa2291d74', '0x8703BDb1b413060a13c2f4712A30ADC86B34f7Ce',
                    '0x3Ee9201B37eb55e108836ae15EFaeF1Ec33C6ea9', '0x62e4E2fbe5Da0564AADbAcF09c6e064cc0215488',
                    '0x563D127CAC8Ac56edd36e9BCa18012BDadbf0a21', '0x0EdDE1EdfAAeBD07CECa83e3E2D30f0e3e740C9b',
                    '0x1152d9607c9D42b21C15c1195c7766061a580E96', '0xee2826453A4Fd5AfeB7ceffeEF3fFA2320081268',
                    '0x3953d3428719936ef11DF10466db89A0Ea4A9b25', '0xA06255BA0E8869F8D1ACC2B3dE56cDFc726b6666',
                    '0x6D6A96B3c7634CBb319aEEC90d809C96f81E84fE', '0x6Ea9a3D68AaE7aB9b0C8804f585f7CB11F6E4Aac',
                    '0x967219b8162529131e8C6056Aa9D5A7a85247812', '0x4309d925244812E4457496515A0Cd57741d43A87',
                    '0xB72C8Bf1Ca1714753AB376b53000Db917964Dc28', '0xBE7C438e8DC135Ca5f0f1070b7edeA5d22FeeB7f',
                    '0x5CD9765c799e468eA51591a69C245B09f1eBb690', '0xD1Abe5DB14d073883f2084c2aF105652102BDefc',
                    '0x99089423F5A1f24396290ac5828F59f97933f4ED', '0xEE195294053998D024aa9292bC7cFD5A9F89398D'}
LYBRA_ABI = [
    {"type": "function", "name": "depositedAsset", "constant": False, "anonymous": False, "stateMutability": "view",
     "inputs": [{"name": "", "type": "address", "storage_location": "default", "offset": 0,
                 "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
                 "simple_type": {"type": "address"}}], "outputs": [
        {"name": "", "type": "uint256", "storage_location": "default", "offset": 0,
         "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
         "simple_type": {"type": "uint"}}]},
    {"type": "function", "name": "getBorrowedOf", "constant": False, "anonymous": False, "stateMutability": "view",
     "inputs": [{"name": "user", "type": "address", "storage_location": "default", "offset": 0,
                 "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
                 "simple_type": {"type": "address"}}], "outputs": [
        {"name": "", "type": "uint256", "storage_location": "default", "offset": 0,
         "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
         "simple_type": {"type": "uint"}}]},
    {"type": "function", "name": "getAssetPrice", "constant": False, "anonymous": False,
     "stateMutability": "nonpayable", "inputs": [], "outputs": [
        {"name": "", "type": "uint256", "storage_location": "default", "offset": 0,
         "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
         "simple_type": {"type": "uint"}}]},
    {"type": "function", "name": "totalDepositedAsset", "constant": False, "anonymous": False,
     "stateMutability": "view", "inputs": [], "outputs": [
        {"name": "", "type": "uint256", "storage_location": "default", "offset": 0,
         "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
         "simple_type": {"type": "uint"}}]},
    {"type": "function", "name": "getPoolTotalCirculation", "constant": False, "anonymous": False,
     "stateMutability": "view", "inputs": [], "outputs": [
        {"name": "", "type": "uint256", "storage_location": "default", "offset": 0,
         "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
         "simple_type": {"type": "uint"}}]},
    {"type": "function", "name": "superLiquidation", "constant": False, "anonymous": False,
     "stateMutability": "nonpayable", "inputs": [
        {"name": "provider", "type": "address", "storage_location": "default", "offset": 0,
         "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
         "simple_type": {"type": "address"}},
        {"name": "onBehalfOf", "type": "address", "storage_location": "default", "offset": 0,
         "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
         "simple_type": {"type": "address"}},
        {"name": "assetAmount", "type": "uint256", "storage_location": "default", "offset": 0,
         "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
         "simple_type": {"type": "uint"}}], "outputs": []},
    {"type": "function", "name": "liquidation", "constant": False, "anonymous": False, "stateMutability": "nonpayable",
     "inputs": [{"name": "provider", "type": "address", "storage_location": "default", "offset": 0,
                 "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
                 "simple_type": {"type": "address"}},
                {"name": "onBehalfOf", "type": "address", "storage_location": "default", "offset": 0,
                 "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
                 "simple_type": {"type": "address"}},
                {"name": "assetAmount", "type": "uint256", "storage_location": "default", "offset": 0,
                 "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
                 "simple_type": {"type": "uint"}}], "outputs": []}
]
EUSD_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {"type": "function", "name": "decimals", "constant": False, "anonymous": False,
     "stateMutability": "pure", "inputs": [], "outputs": [
        {"name": "", "type": "uint8", "storage_location": "default", "offset": 0,
         "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
         "simple_type": {"type": "uint"}}]}]
LYBRA_CONTRACT_ADDRESS = '0xa980d4c0C2E48d305b582AA439a3575e3de06f0E'  # ← 你的ERC20合约地址
EUSD_CONTRACT_ADDRESS = '0xdf3ac4F479375802A821f7b7b46Cd7EB5E4262cC'
NODE_URL = 'https://eth-mainnet.g.alchemy.com/v2/r8aq919e-3HfTzAPXTYPZxRBLu_kZw-A'
# NODE_URL = 'https://virtual.mainnet.rpc.tenderly.co/0bd09288-f95c-4d59-9d0c-8172952140f3'
# NODE_URL = 'https://mainnet.infura.io/v3/42d116ef28d84f0c99f9873f4eb0d7c0'
# NODE_URL = 'https://rpc.tenderly.co/fork/90dc85bc-f2f6-4816-adab-0e44465ec873'
# NODE_URL = 'https://mainnet.gateway.tenderly.co/7aTTDUXsphVy5fWhOnfor1'
w3 = Web3(Web3.HTTPProvider(NODE_URL))
w3.eth.account.enable_unaudited_hdwallet_features()
chainId = w3.eth.chain_id
with open('PRIVATE_MNEMONIC', 'r') as f:
    PRIVATE_MNEMONIC = f.read()
ACCOUNT = w3.eth.account.from_mnemonic(PRIVATE_MNEMONIC)  # .from_key(PRIVATE_KEY)
WALLET_ADDRESS = ACCOUNT.address
contract_lybra = w3.eth.contract(address=Web3.to_checksum_address(LYBRA_CONTRACT_ADDRESS), abi=LYBRA_ABI)
contract_eusd = w3.eth.contract(address=Web3.to_checksum_address(EUSD_CONTRACT_ADDRESS), abi=EUSD_ABI)
badCollateralRatio = 150000000000000000000
session = requests.Session()
session.headers = {'Content-Type': 'application/json'}


def send_msg(msg):
    try:
        print(msg)
        json_msg = {
            "msgtype": "text",
            "text": {'content': msg}
        }
        session.post(
            url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=6f2ec864-c474-4c8f-b069-1e3c35eb7d73',
            json=json_msg)
    except:
        return


async def provider():
    print(datetime.now(), '开始扫描')
    target_address_set = set()

    async def onBehalfOfAddress(target_address):
        try:
            borrowed = await asyncio.to_thread(contract_lybra.functions.getBorrowedOf(target_address).call)
            if not borrowed:
                return
            depositedAsset = await asyncio.to_thread(contract_lybra.functions.depositedAsset(target_address).call)
            assetValue = depositedAsset * assetPrice
            onBehalfOfCollateralRatio = (assetValue * 100) / borrowed
            print(target_address, onBehalfOfCollateralRatio / 10e19, assetValue / 10e35)
            if onBehalfOfCollateralRatio >= badCollateralRatio or assetValue * 0.1 / 10e27 <= w3.eth.gas_price * 1.3:
                return
            target_address_set.add((target_address, onBehalfOfCollateralRatio, depositedAsset))
            send_msg(f'清算地址:{target_address}')
        except:
            return

    def keeper(arg):
        try:
            # 查询余额
            eusdAmount = contract_eusd.functions.balanceOf(WALLET_ADDRESS).call()
            target_address, onBehalfOfCollateralRatio, depositedAsset = arg
            if superLiquidation and onBehalfOfCollateralRatio < 125 * 1e18:
                assetAmount = int(min(eusdAmount * 1e18 / assetPrice, depositedAsset))
            else:
                assetAmount = int(min(eusdAmount * 1e18 / assetPrice, depositedAsset / 2))
            if superLiquidation:
                tx = contract_lybra.functions.superLiquidation(
                    WALLET_ADDRESS, target_address, assetAmount
                )
            else:
                tx = contract_lybra.functions.liquidation(
                    WALLET_ADDRESS, target_address, assetAmount
                )
            tx = tx.build_transaction({
                'chainId': chainId,  # 主网
                'gas': 1000000,
                'gasPrice': int(w3.eth.gas_price * 1.3),  # 根据网络情况调整
                'nonce': w3.eth.get_transaction_count(ACCOUNT.address),
            })
            # 签名交易
            signed_tx = ACCOUNT.sign_transaction(tx)
            # 发送交易
            tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            print(f"交易哈希: {tx_hash.hex()}")
            send_msg(f"清算哈希: {tx_hash.hex()}")
            if tx_hash:
                # 等待确认
                receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
                print(f"Approve confirmed in block {receipt['blockNumber']}")
        except:
            traceback.print_exc()

    # address_borrowed = ['0x7E6601A0Cb2B5aE129c09661846a053ea07223Fb']
    while 1:
        try:
            assetPrice = contract_lybra.functions.getAssetPrice().call()
            totalDepositedAsset = contract_lybra.functions.totalDepositedAsset().call()
            poolTotalCirculation = contract_lybra.functions.getPoolTotalCirculation().call()
            overallCollateralRatio = (totalDepositedAsset * assetPrice * 100) / poolTotalCirculation
            if overallCollateralRatio < badCollateralRatio:
                superLiquidation = True
            else:
                superLiquidation = False
            break
        except:
            await asyncio.sleep(300)
            continue
    await asyncio.gather(*[onBehalfOfAddress(target_address) for target_address in address_borrowed])
    target_address_set = sorted(target_address_set, key=lambda x: x[-1], reverse=True)
    for a in target_address_set:
        keeper(a)
        break


async def main():
    await provider()
    # 设置任务调度
    scheduler.add_job(provider, 'cron', hour='*', minute='*/15', second='00', timezone='Asia/Shanghai')
    # 启动调度器
    scheduler.start()
    stop_event = asyncio.Event()
    await stop_event.wait()  # 等待事件触发


if __name__ == "__main__":
    scheduler = AsyncIOScheduler()
    asyncio.run(main())
