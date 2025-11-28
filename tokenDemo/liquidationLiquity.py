import asyncio
import traceback
from datetime import datetime

import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from web3 import Web3

address_borrowed = {'0xa850535D3628CD4dFEB528dC85cfA93051Ff2984', '0x6069a2cd9b1250e54EAfFB6Af436E71D6742E225',
                    '0x98d87F3BF35B8D5685e1eDfAeb8BA2F7d0a7fB11', '0x84E546441FAA3699B2bd5d006901fA99428f20Cc',
                    '0xA1CbA1fCEf2CD7379f74fEec9a7d8B17d430cc6f', '0xD193A16754a4D2E8b0F0dE36e1Ca18134F4B5C51',
                    '0x8FA719C9d89E4c6D7520AA0aFF36D5631d4Ac5D4', '0x92985E3fcA42C7619464cA00d1824189F6078A84',
                    '0x513EC639bED7c8E65d746D0120fC9095ad44498E', '0x7f88339Cdb21Fe3D60b6D3f285f266adb103aA03',
                    '0x1ce04A0A1Eb0BAe1D48159608dD11DCFdBAC2310', '0x9e726212BE073Dd7FC54284bC6fdd7af67bb2f5a',
                    '0x97944E369a1Af4040816f157134eDCA8E9F82eCD', '0xDdf3679cF581bC66F491b01Ab6742310Aedb1a1C',
                    '0x14CA5d1C38FD3799deFfe8FF0Ca09C4b834d2E15', '0xB304712Dd71799F05Aa8225F1588E2cF8E8Da21A',
                    '0xEB1A6D66bCD3D3d9E34672c73020c1Fe2d64DbeB', '0xC0635F6318b8b19b8ED3902b6F4987F9419E7c9d',
                    '0xF9324746FcDC2e018D7fEac2293490Ddbab56759', '0xa46A190a900F4C24D33F199DC54C17D4778E7C65',
                    '0xD1B0e5aDA9BEb183404Cd45177A1b6D347516144', '0x75cFe89fC94C9E6D36cF65e09953A9E5D977d030',
                    '0xF1252Af072725858fBF1Ce3c3EDcdAe3dF87BDe4', '0x60E69297E961794D226d01695619B019dCeE1eF8',
                    '0xFD7E12562435bc4B842b19133bE76f3FB231DC5e', '0x654239B299759A7d0b364C27943dE9087067Bd71',
                    '0x6696bF74546BF826F58d5893Ec74B98257966335', '0xfe28850e1262b5a3d8Ac95A2260D64bBb2ac52d0',
                    '0x96BB84D8D4319E854b224682C857CFD4E504D22a', '0xCa5B42f5058cF62edd84C9D2449DD82d5B0a71e9',
                    '0x2361b944e6E2D3554154F91873128F050ae4242A', '0xEE49Ce60f12985E0e4b8D9e09e7B09B98Ee39dfd',
                    '0x8b32B71F2A7096019c2E0cd289ae0bdA493FF792', '0x2b2411BD9Dcfb0d3F375521917e623676987dFb1',
                    '0x29b2C24F61c77e33190d1e7b7533B490A35776B5', '0xb96c0B4fa78813dCa40c3a42Ee1E30583D85001B',
                    '0x1b32e25318C7E2C03Abf6E87cD679db884Ea98fd', '0x462Cc75Caee4d0bE283EEdDbc2cD5698b9880b91',
                    '0xd2f92747e7AEb37ffb1d504012901a2aef34b39C', '0xF0F0BfA520E83Dc7F44a1e15eb4e42e29Aef297A',
                    '0x290eEE9E135d6547Acf30D8eB3FDEE4069De4883', '0xB94EC25d29e202394bB73E758487402a00dAaf1d',
                    '0x1D83B223b68266C18762ce37000B1080B4DD3979', '0x11FFe9Ef471530394B781839E2370c0778c5cDDB',
                    '0xa71C886f8607c9a8B0bac4991B6D4F2da041df26', '0x6205C2D8482Bec5faE564DB967F9636D7529454a',
                    '0x7D3894d3E8A8e504B1FA66AE506e8B15B3E900b4', '0x76eb7232943AAe8546440A945C2D6bDd146C0299',
                    '0xEb613bf4f4f4B49063350c7fD57f7A99e41c6538', '0x261312B63eA13933d777047a0781AB4D8de130e5',
                    '0x0C6AAd736E283F6613bF8aCC3f41dfEb15629889', '0x78154cb1629b851578A55094be792857b9709e02',
                    '0x6C26A07CcfF2783577ee911d4C6907cF59775554', '0x1125917201ed36700F86c3CecEC8C5DAfAe280D1',
                    '0x268bb6Aaa0A7414ce71F7e7FA52D99b0FfAeB6E1', '0x218Ba29889306fdFf40ddf6aBEB42a32e7BA61f8',
                    '0xdfBca62B0D9d7c90A9192674d715e33683551aC7', '0xB4384C46248bc57531520c88F31032AFFCF3bd1F',
                    '0xb62F4f38bCA544DEDEA1d1e1b00e802Fe13fBfC7', '0x721792A27797A8F286fcb40d5F644C52bFc1DdBd',
                    '0x2291F52bddc937b5B840d15E551e1DA8C80c2B3c', '0x1dD04D737b29a2c449367eaD37981c9A7492C9F0',
                    '0xAcEF3B48436f7d9aC367B320d67Df899B09bFFC7', '0x68A9857B0E540E5a800151D3E4A33037191A5Dc4',
                    '0x53C61cfb8128ad59244E8c1D26109252ACe23d14', '0x262D4ff9641d13713C0732f9649f9D88d71F7ACb',
                    '0x24Dec122E8b7233F72Ec65996890b97eBC29F4bd', '0x9467C3068563b4d992f0850A8eab03e48D4535D3',
                    '0x53F98DE2c91274d9CC6647f590c2e4722C637ECd', '0x39a6afc920EAb4722Cf217ba84644eBD6adeCf15',
                    '0x69e627ac4eEDbAce4Fa1fAFbEec5539d124b3679', '0x4640E70ee2eA7273Fa04D771593e760455f8bf78',
                    '0x12e90F27b415CCd82307ed88Cb6477E9dB4e039C', '0xDF5B9374AB6B8fF23499214Be5B4F942719895e8',
                    '0x9443E528d2BddfDfE38e1AEf3fA8447E291f0c60', '0x0ad087203f334832522F70fdB8F19aC78AF3384c',
                    '0x002aE0Cf6f65e80a260278d3caF125c3242cdB65', '0xCF604b4Dfe6E75cFF5D01aE8973252C88366D1b0',
                    '0x4E766Ac0CFd605C154147E16FE1B4Bacd43CcB3c', '0x77e0441e260361E0792c1C0Fb7DCEf9b8B900dF0',
                    '0xef62586F8bDb5452aE80F3eb2Ac577de3099E87f', '0xCB16F82E5949975f9Cf229C91c3A6D43e3B32a9E',
                    '0x8d3B724e9e448914A821B8b0ef259c77Db5a3353', '0x892a0CA4F011269D9B05722AdDcCDb65AD9CB226',
                    '0x8dFD545A2d6Ba57D0CCfb060a0EEfE01f41f2902', '0x1384b4515544e520956e4FA7F5A10C7fb0AC3729',
                    '0x35F8a4F1E964CC339420700c6548339DB0F59609', '0x8F44e2CcBF1C358cc9604E15ED61a7752ed31c2B',
                    '0xf2F3C3898F817b549c234430c087200904A1938D', '0x7C96d96f75aB37F5bfa841D9f5D345bAfcFD5b30',
                    '0x5bB679e29A437ebf006E6df62766BE59624EA0C6', '0x02F729E81bA34d64259Ed99BB43bCfe7EF27Fc7d',
                    '0xE76bc1cC2a58176249d92be86D988470b8c5760e', '0x903628bf8e703766277279CA8eB7BfB5e32107A5',
                    '0xcabc0E1EebD9fC9eC64d47a06CB2D43792e1977b', '0x8146722Bc3a6cEA47b4DDa6B66310A002998D95E',
                    '0x3594141c2aA65409642716C7075785FDC9704A9A', '0xc2008b64e04F2a878bF58e51e524C014EEC1Dcb0',
                    '0xA1fB632E11FB300cba18Da19525F6730e8D68Fef', '0x26bb5D5c90C9427f506EBf16fBfDDb060478685F',
                    '0x2306120Ff6AD65c222E5Cf27B703A7eB850145Ee', '0xE3935519Abc87C090DD95Ad593Aa2AeF10A9c409',
                    '0xBF4aAA3B25359e3A2050261270EBA09f7A4DCA6A', '0x9D4512C43C580BE2d6a7517d6777Fac46131a9d6',
                    '0x58D9A499AC82D74b08b3Cb76E69d8f32e1395746', '0x99282E50Ef8b2e632900f23F747f48E5317fE7eB',
                    '0x954f2a8b86Aa586c3Cc3a2088B72e2a560D7Dc22', '0xd53b196175492Eb41F861C8ec65BeecB3D5e4A2E',
                    '0xF74b37D9bc9049d26724F25C7961D1aC4e1Fa76C', '0x93baEE01B1008B6D9F0B29D64C896D6f2B9F91E9',
                    '0xc10e9Eb244f64a183805D9Af13BFd565A4718758', '0x7FE6e94FC0d5019A954d71d8dc350BCeDC9a48aa',
                    '0xD4FbcC485A8b6ECB7dbBC579f6fc7aEc8126DCE8', '0xaf07e85591Dc02A6E54604b4313CF2f92f27174F',
                    '0xd1D0A6FE11E2465CBeaf9F86ae3036637C842dC7', '0x84123d4FeE859341D96D0b322afC889e206Ca507',
                    '0xCD3F3DD2893Ed22b2dEc80f6144F9B0EcD6A3418', '0xFB68E6B3562a6a569e4731E055b62bbBb81d9d1E',
                    '0x04Fa59CCc9a4CE654A94701352c496Aae3F82578', '0x8B4B889cd88AE68205D620678373B1DeE08E775A',
                    '0xE1137eE95345037529eA444985F7634Bd05a3C8C', '0x5e6DB990e535de7CdaBEc91893758BC7b3d37890',
                    '0xFc7A4653c19B529772c033D92A525db05FDF9723', '0xd94C214F7CF6C162e4eC9d622Fe6fc432e89406F',
                    '0xD2b2fF8dDc7AeC8EB2666E497E3296c6e4A62F81', '0x57Ef012861c4937A76B5D6061bE800199A2b9100',
                    '0xD181B1488366661202b8953fB5BeaD066CC5886C', '0xEd42E2B0269B59Ed86Ca32Dcf46b41a5ce0Ec869',
                    '0xb60d601606351dC78a4f5493aa2AacC06A3B19E3', '0xc7718CFa793ddC5d012740a4F7b2c7DD8f793A4e',
                    '0x959b947197A98B7265CC03d1601f36c67067409F', '0x7Cad02C1E53deCF5d1102A4B9bee5de79c6D2E18',
                    '0x77eE52B29358386E31765B07396d53229a2079af', '0xe3C090F6F8Ce7b69bA6957692Af1aDe1DE745020',
                    '0xb7Ad9AE55861329d95906cFf40B6Fa93Fd36e436', '0xbAF230E1792b548aec3F69ed19fccDFC9F7807BE',
                    '0x1b277Ae7fAf0e08f53D1a90285d8D0236E0B59bF', '0xE0440cc2CDc7D5B5bC99cF110ED0CbEEffb04513',
                    '0x5FBDB238A05ed167C1A61F7A34189cAd837f2Af6', '0xd88898D6a320e03E2d2a4CEa58E0aF793598107a',
                    '0x2489ac126934D4d6a94Df08743Da7b7691e9798E', '0xaC5406AEBe35A27691D62bFb80eeFcD7c0093164',
                    '0x97c8A59d243638081d6f3562DeBdcFc04d60B897', '0x8B41Bc8B19e0b8E6C23e5B576877A17AdB200a71',
                    '0x889910125a2ef56f4a5d655222F01522c9d7F56A', '0xb2F31D646D2C9d056dd97558F493bdC6e92489cf',
                    '0x1F4B693716434E7BD50f7383C41784edCF0278F6', '0xdC7Ea55de25D95b727dEf66738Ff932D8962500a',
                    '0xb6629Cf592D4aeE5Fde0A485443e61Cd03c19148', '0x4062F22a043Be4123C487Dd67a88FeBc7B48756F',
                    '0x820E72515f48d78C46807767bccB3037d75d9706', '0x4EF267Fb114b38bdBdBC5ea8aEAB1236608BE798',
                    '0x48d21Dc6BBF18288520E9384aA505015c26ea43C', '0xc0e12A9B712f91f79e6bb718C86DCc6B7a5A36D4',
                    '0x8EB2E0cebcD191625037a042C9edF67b7F7FD74C', '0x59D9Ea3FD0E8303eCEb1f151cca5563a737498Ff',
                    '0xBFb148aB6678bBf4463590a98f5A87a2D094EdA9', '0xDD78F2764674E70C0cFEb15E4A8d0af0e8b364B1',
                    '0x441497e2FC4E697D1d604204dC8E1d1D992c9684', '0x62F69D9157fDeeF75C82Ed957E7B177d3CE55eFE',
                    '0x0Fd0489d5CcF0AcC0ccbE8a1F1e638E74CaB5BD7', '0x6D3709BA7d09428b76f4Ec604f60A3Ca336c78B2',
                    '0xaA6aa84452b7325C55DF93690233C7fb8DF7CF65', '0x8D6154ac6E171a458C89971A71d737e4d3a6B19B',
                    '0x54Bc1c2C0fCaEdcC2e68C97774F4F873C1d24d08', '0xa3C7F057aB499f26974024cb136C1ccc8c44D53B',
                    '0xFA426e2e421C4FA905083bFdA0e3a0FA017f3a28', '0x842ecBAA58d996B19fc9b0b66f9B8DF4b98080fA',
                    '0xA3cc97cFcB38A8b1Cac7DC7692557c305d6Ac75F', '0xb42884463079951DEDf4F8840d5Fd610c3eC6D94',
                    '0x29e99312e9B87b39d22601Ac009Ba04142014f0E', '0x0f2b381c99B48914caB5efBEeF38fcCc3ccd894a',
                    '0x0653A6CA0c0cF8FD243EB423E0D4C105218Ac334', '0xF7D926db782dDB5DF45E2e68A32e6cf380400266',
                    '0x7AFd32d27FC1a7f05673a199Db4Df3051084D3eE', '0x8B0C8c18993a31F57e60d81761F532Ef14633153',
                    '0x0ddC6D7cEA2F36AA37011cD7e8CebA3dCf60d15B', '0x4625f1bcf774b5D8e0Cc009C10ea0615DabB2688',
                    '0xCFb5F1A901814BDFb6b5E808C9eb940b9e07fD12', '0x56356AfABaa06B555029a1f1FeE3FCecf21D3692',
                    '0x423eDA6652d0636930D350CB60A01EB1F45AFC3F', '0xF05d1dAc897318AFA83f1650C500ba4bB638bCc2',
                    '0xbb5beBb7c3390b9Deb07e321b5ce046E9640737E', '0x555B66034f175BC31fF142306fB2F3073E5fB678',
                    '0x7f9095575034Fadc9BCAEb29C5157C9C6A8D89ba', '0x65d3D3bBc94d357E3B3c05C208F7e6944eE7EAD9',
                    '0xc1C589dc0922399b966f515d4b6436707d679974', '0xA3AFc6aC0D7f6b8cafEFef730105B389CfB5A2B9',
                    '0x3170bD1144e67E4F146a22A1307C1D10B9F4aB81', '0x719b1cA972F8E89A46e5b72d9928B48d1007bBa0',
                    '0x776F70c099B670459612eC9D8f6e578B364d3595', '0x308c5A2713154412da157d69095f3DB09336D627',
                    '0x197A78Fe1bD3BBb64c1325c027bdE8F67Bac1770', '0x53fecF0779872fd5648F87898da170f14b51C966',
                    '0xc688a50acd33CdCBa91760f58290FaB20bC11095', '0x13f073Bb6338036649E16E256F31784666a8FbbB',
                    '0x5C193bBEF8B1b1EaBA63754A3284e364f4E36767', '0xDF8a470714c3CA1a9C58c0Bd33cbE6E1f9741C0d',
                    '0xDdFE74f671F6546F49A6D20909999cFE5F09Ad78', '0xa7c2B68Fe04cD448BCCd582063DeEb2dcE70143b',
                    '0x452Cc5141707Ed1986158f6C89d2fFe11edC8A0C', '0x6a70d5f854B92FAA05Ccd7E9022b82268a54e9D9',
                    '0xbb8c4751F50CFeF766E7F158a68c348f3441A62B', '0x05a5713767312f3481831bDc20d47997D71C0501',
                    '0xE5410A2d21e6984F734dEa92C3E343FafA95abad', '0xD41Bafb7f393D9364A261eac5C760Ad65ee7e94c',
                    '0xD98C3b7f0297f2eD1861893cFD80C4CfA24Fb687', '0x3CD48a0cB9c82608E743086B1ffda59741Beef3F',
                    '0xeA87bA3a9bb08d425E5ECe55C88F7580C989A2F9'}
LYBRA_ABI = [
    {"type": "function", "name": "getAssetPrice", "constant": False, "anonymous": False,
     "stateMutability": "nonpayable", "inputs": [], "outputs": [
        {"name": "", "type": "uint256", "storage_location": "default", "offset": 0,
         "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
         "simple_type": {"type": "uint"}}]},
]
LIQUITY_ABI = [
    {"type": "function", "name": "getTroveStatus", "constant": False, "anonymous": False, "stateMutability": "view",
     "inputs": [{"name": "_borrower", "type": "address", "storage_location": "default", "offset": 0,
                 "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
                 "simple_type": {"type": "address"}}], "outputs": [
        {"name": "", "type": "uint256", "storage_location": "default", "offset": 0,
         "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
         "simple_type": {"type": "uint"}}]},
    {"type": "function", "name": "getCurrentICR", "constant": False, "anonymous": False, "stateMutability": "view",
     "inputs": [{"name": "_borrower", "type": "address", "storage_location": "default", "offset": 0,
                 "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
                 "simple_type": {"type": "address"}},
                {"name": "_price", "type": "uint256", "storage_location": "default", "offset": 0,
                 "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
                 "simple_type": {"type": "uint"}}], "outputs": [
        {"name": "", "type": "uint256", "storage_location": "default", "offset": 0,
         "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
         "simple_type": {"type": "uint"}}]},
    {"type": "function", "name": "liquidate", "constant": False, "anonymous": False, "stateMutability": "nonpayable",
     "inputs": [{"name": "_borrower", "type": "address", "storage_location": "default", "offset": 0,
                 "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
                 "simple_type": {"type": "address"}}], "outputs": []},
    {"type": "function", "name": "MINUTE_DECAY_FACTOR", "constant": False, "anonymous": False,
     "stateMutability": "view", "inputs": [], "outputs": [
        {"name": "", "type": "uint256", "storage_location": "default", "offset": 0,
         "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
         "simple_type": {"type": "uint"}}]},
    {"type": "function", "name": "getTroveFromTroveOwnersArray", "constant": False, "anonymous": False,
     "stateMutability": "view", "inputs": [
        {"name": "_index", "type": "uint256", "storage_location": "default", "offset": 0,
         "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
         "simple_type": {"type": "uint"}}], "outputs": [
        {"name": "", "type": "address", "storage_location": "default", "offset": 0,
         "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
         "simple_type": {"type": "address"}}]},
    {"type": "function", "name": "getTCR", "constant": False, "anonymous": False, "stateMutability": "view", "inputs": [
        {"name": "_price", "type": "uint256", "storage_location": "default", "offset": 0,
         "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
         "simple_type": {"type": "uint"}}], "outputs": [
        {"name": "", "type": "uint256", "storage_location": "default", "offset": 0,
         "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
         "simple_type": {"type": "uint"}}]},
]
LYBRA_CONTRACT_ADDRESS = '0xa980d4c0C2E48d305b582AA439a3575e3de06f0E'  # ← 你的ERC20合约地址
LIQUITY_CONTRACT_ADDRESS = '0xA39739EF8b0231DbFA0DcdA07d7e29faAbCf4bb2'
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
contract_liquity = w3.eth.contract(address=Web3.to_checksum_address(LIQUITY_CONTRACT_ADDRESS), abi=LIQUITY_ABI)
badCollateralRatio = 1100000000000000000
session = requests.Session()
session.headers = {'Content-Type': 'application/json'}


# for i in range(209):
#     address_borrowed.append(contract_liquity.functions.getTroveFromTroveOwnersArray(i).call())
# print(address_borrowed)


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
            status = await asyncio.to_thread(contract_liquity.functions.getTroveStatus(target_address).call)
            if not status:
                return
            icr = await asyncio.to_thread(contract_liquity.functions.getCurrentICR(target_address, assetPrice).call)
            print(target_address, icr / 10e15)
            if icr >= badCollateralRatio:
                return
            target_address_set.add(target_address)
            send_msg(f'liquity V1清算地址:{target_address}')
        except:
            return

    def keeper(target_address):
        try:
            tx = contract_liquity.functions.liquidate(target_address)
            gas_price = int((w3.eth.get_block('latest')[
                                 'baseFeePerGas'] + w3.eth.max_priority_fee * 10e2) * 1.3)
            tx = tx.build_transaction({
                'chainId': chainId,  # 主网
                'maxFeePerGas': gas_price,
                'maxPriorityFeePerGas': gas_price,
                'gas': 2000000,
                'nonce': w3.eth.get_transaction_count(ACCOUNT.address),
            })
            # 签名交易
            signed_tx = ACCOUNT.sign_transaction(tx)
            # 发送交易
            tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            print(f"V1交易哈希: {tx_hash.hex()}")
            send_msg(f"V1清算哈希: {tx_hash.hex()}")
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
            overallCollateralRatio = contract_liquity.functions.getTCR(assetPrice).call()
            if overallCollateralRatio < badCollateralRatio:
                superLiquidation = True
            else:
                superLiquidation = False
            break
        except:
            await asyncio.sleep(300)
            continue
    await asyncio.gather(*[onBehalfOfAddress(target_address) for target_address in address_borrowed])
    for a in target_address_set:
        keeper(a)
        break


async def main():
    await provider()
    # 设置任务调度
    scheduler.add_job(provider, 'cron', hour='*', minute='*/59', second='00', timezone='Asia/Shanghai')
    # 启动调度器
    scheduler.start()
    stop_event = asyncio.Event()
    await stop_event.wait()  # 等待事件触发


if __name__ == "__main__":
    scheduler = AsyncIOScheduler()
    asyncio.run(main())
